"""
ui/interface.py
---------------
Aplicação Flask que serve a interface web e expõe as rotas da API interna.

Cada rota é um handler fino: valida entrada, chama a camada de domínio
correta e devolve JSON ou arquivo. Nenhuma lógica de negócio vive aqui.

Rotas
-----
GET  /                          — Página principal (SPA)
GET  /api/users                 — Lista todos os usuários
GET  /api/users/<id>/posts      — Posts + métricas de um usuário
GET  /api/export/csv            — Download do CSV
GET  /api/export/xlsx           — Download do Excel
POST /api/report/send           — Simula envio do relatório
"""

from __future__ import annotations

import asyncio
from typing import Any

from flask import Flask, Response, jsonify, render_template, request, send_file
import io

import config
from api.client   import HttpClient, MemoryCache, ApiError
from api.endpoints import get_users, get_posts_with_comments
from analytics.metrics import compute_metrics
from export.csv_exporter  import to_csv_bytes, build_report_row
from export.xlsx_exporter import to_xlsx_bytes
from export.report_sender import send_report


# =============================================================================
# Inicialização
# =============================================================================

app = Flask(__name__, template_folder="templates")

# Cache e client compartilhados pela vida da aplicação
_cache  = MemoryCache()
_client = HttpClient(cache=_cache)


# =============================================================================
# Helpers
# =============================================================================

def _run(coro: Any) -> Any:
    """Executa uma corrotina no event loop atual ou cria um novo.

    Flask é síncrono por padrão; este helper permite chamar código
    assíncrono sem migrar toda a aplicação para Flask assíncrono.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Ambiente de teste ou loop externo já ativo
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


def _error(message: str, status: int = 500) -> tuple[Response, int]:
    return jsonify({"error": message}), status


def _parse_filters() -> tuple[int, int]:
    """Extrai e valida os filtros da query string."""
    try:
        min_chars = max(0, int(request.args.get("min_chars", config.DEFAULT_MIN_CHARS)))
        min_posts = max(0, int(request.args.get("min_posts", config.DEFAULT_MIN_POSTS)))
    except ValueError:
        min_chars = config.DEFAULT_MIN_CHARS
        min_posts = config.DEFAULT_MIN_POSTS
    return min_chars, min_posts


# =============================================================================
# Rotas
# =============================================================================

@app.route("/")
def index() -> str:
    """Serve a SPA principal."""
    return render_template("index.html")


@app.route("/api/users")
def api_users() -> tuple[Response, int]:
    """Retorna a lista de usuários da API externa."""
    try:
        users = _run(get_users(_client))
        return jsonify(users), 200
    except ApiError as exc:
        return _error(str(exc), exc.status_code or 502)
    except Exception as exc:
        return _error(f"Erro inesperado: {exc}")


@app.route("/api/users/<int:user_id>/posts")
def api_user_posts(user_id: int) -> tuple[Response, int]:
    """Retorna posts enriquecidos + métricas calculadas para um usuário.

    Query params
    ------------
    min_chars : int  — mínimo de caracteres por post (default: 0)
    min_posts : int  — limiar de posts para status ativo (default: 5)
    """
    min_chars, min_posts = _parse_filters()

    try:
        posts   = _run(get_posts_with_comments(_client, user_id))
        metrics = compute_metrics(posts, min_chars=min_chars, min_posts=min_posts)

        return jsonify({
            "raw_total":    metrics.raw_total,
            "total_posts":  metrics.total_posts,
            "avg_chars":    metrics.avg_chars,
            "avg_comments": metrics.avg_comments,
            "is_active":    metrics.is_active,
            "status":       metrics.status,
            "posts": [
                {
                    "id":             p["id"],
                    "title":          p["title"],
                    "body_length":    len(p.get("body", "")),
                    "comment_count":  p.get("_comment_count", 0),
                }
                for p in metrics.filtered_posts
            ],
        }), 200

    except ApiError as exc:
        return _error(str(exc), exc.status_code or 502)
    except Exception as exc:
        return _error(f"Erro inesperado: {exc}")


@app.route("/api/export/csv")
def api_export_csv() -> Response:
    """Gera e devolve o CSV do relatório do usuário selecionado.

    Query params
    ------------
    user_id   : int  — ID do usuário
    user_name : str  — Nome do usuário (para evitar segunda busca)
    min_chars : int
    min_posts : int
    """
    user_id   = request.args.get("user_id",   type=int)
    user_name = request.args.get("user_name", type=str, default="Usuário")

    if not user_id:
        return _error("user_id obrigatório", 400)[0]

    min_chars, min_posts = _parse_filters()

    try:
        posts   = _run(get_posts_with_comments(_client, user_id))
        metrics = compute_metrics(posts, min_chars=min_chars, min_posts=min_posts)
        row     = build_report_row({"id": user_id, "name": user_name}, metrics)
        csv_bytes = to_csv_bytes([row])

        return Response(
            csv_bytes,
            mimetype="text/csv",
            headers={
                "Content-Disposition":
                    f"attachment; filename={config.EXPORT_FILENAME_BASE}.csv"
            },
        )
    except ApiError as exc:
        return _error(str(exc), exc.status_code or 502)[0]
    except Exception as exc:
        return _error(f"Erro inesperado: {exc}")[0]


@app.route("/api/export/xlsx")
def api_export_xlsx() -> Response:
    """Gera e devolve o Excel do relatório do usuário selecionado."""
    user_id   = request.args.get("user_id",   type=int)
    user_name = request.args.get("user_name", type=str, default="Usuário")

    if not user_id:
        return _error("user_id obrigatório", 400)[0]

    min_chars, min_posts = _parse_filters()

    try:
        posts      = _run(get_posts_with_comments(_client, user_id))
        metrics    = compute_metrics(posts, min_chars=min_chars, min_posts=min_posts)
        row        = build_report_row({"id": user_id, "name": user_name}, metrics)
        xlsx_bytes = to_xlsx_bytes([row])

        return send_file(
            io.BytesIO(xlsx_bytes),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"{config.EXPORT_FILENAME_BASE}.xlsx",
        )
    except ApiError as exc:
        return _error(str(exc), exc.status_code or 502)[0]
    except Exception as exc:
        return _error(f"Erro inesperado: {exc}")[0]


@app.route("/api/report/send", methods=["POST"])
def api_send_report() -> tuple[Response, int]:
    """Simula o envio do relatório via POST para /reports (Task 5).

    Body JSON
    ---------
    {
      "user_id":   int,
      "user_name": str,
      "min_chars": int,
      "min_posts": int
    }
    """
    body = request.get_json(silent=True) or {}

    user_id   = body.get("user_id")
    user_name = body.get("user_name", "Usuário")
    min_chars = max(0, int(body.get("min_chars", config.DEFAULT_MIN_CHARS)))
    min_posts = max(0, int(body.get("min_posts", config.DEFAULT_MIN_POSTS)))

    if not user_id:
        return _error("user_id obrigatório no body", 400)

    try:
        posts    = _run(get_posts_with_comments(_client, user_id))
        metrics  = compute_metrics(posts, min_chars=min_chars, min_posts=min_posts)
        row      = build_report_row({"id": user_id, "name": user_name}, metrics)
        response = _run(send_report(_client, row))
        return jsonify({"success": True, "response": response}), 200

    except ApiError as exc:
        return _error(str(exc), exc.status_code or 502)
    except Exception as exc:
        return _error(f"Erro inesperado: {exc}")
