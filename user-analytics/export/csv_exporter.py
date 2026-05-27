"""
export/csv_exporter.py
----------------------
Geração de relatório em formato CSV.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import config


# =============================================================================
# Funções
# =============================================================================

def build_report_row(
    user: dict[str, Any],
    metrics: Any,  # analytics.metrics.UserMetrics
) -> dict[str, Any]:
    """Monta o dicionário de uma linha do relatório.

    Separado para ser reutilizado pelo exportador Excel e pelo sender.
    """
    return {
        "id_usuario":        user["id"],
        "nome":              user["name"],
        "qtd_posts":         metrics.total_posts,
        "media_chars":       metrics.avg_chars,
        "media_comentarios": metrics.avg_comments,
        "status":            metrics.status,
    }


def to_csv_bytes(rows: list[dict[str, Any]]) -> bytes:
    """Serializa uma lista de linhas do relatório para bytes UTF-8 com BOM.

    O BOM (\\ufeff) garante que o Excel abra o arquivo sem problemas de
    encoding ao dar duplo-clique no CSV gerado.

    Parâmetros
    ----------
    rows:
        Lista de dicionários com as chaves definidas em config.REPORT_COLUMNS.

    Retorno
    -------
    Bytes do CSV prontos para envio via Flask (send_file / Response).
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=config.REPORT_COLUMNS,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)

    return ("\ufeff" + buffer.getvalue()).encode("utf-8")
