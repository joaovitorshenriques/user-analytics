"""
analytics/metrics.py
--------------------
Cálculo puro de métricas sobre posts de um usuário.

Nenhuma função aqui faz I/O ou modifica estado externo — apenas recebe
dados e devolve resultados. Isso facilita testes unitários e reutilização,
da mesma forma que as funções de feature engineering do pipeline são
independentes do modelo LSTM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


# =============================================================================
# Tipos
# =============================================================================

Post = dict[str, Any]


# =============================================================================
# Resultado das métricas
# =============================================================================

@dataclass(frozen=True)
class UserMetrics:
    """Resultado imutável do cálculo de métricas para um usuário.

    Atributos
    ---------
    raw_total:
        Total de posts antes de qualquer filtro.
    filtered_posts:
        Posts que passaram pelo filtro de mínimo de caracteres.
    total_posts:
        Quantidade de posts filtrados.
    avg_chars:
        Média de caracteres do body nos posts filtrados.
    avg_comments:
        Média de comentários por post nos posts filtrados.
    is_active:
        True se raw_total >= min_posts_threshold.
    min_chars_threshold:
        Valor do filtro de caracteres aplicado.
    min_posts_threshold:
        Valor do limiar de posts para status ativo.
    """

    raw_total:          int
    filtered_posts:     list[Post]
    total_posts:        int
    avg_chars:          float
    avg_comments:       float
    is_active:          bool
    min_chars_threshold: int
    min_posts_threshold: int

    @property
    def status(self) -> str:
        return "Ativo" if self.is_active else "Inativo"


# =============================================================================
# Função principal
# =============================================================================

def compute_metrics(
    posts: list[Post],
    min_chars: int = 0,
    min_posts: int = 5,
) -> UserMetrics:
    """Calcula métricas de um usuário a partir de seus posts enriquecidos.

    Parâmetros
    ----------
    posts:
        Lista de posts com campo `_comment_count` injetado por
        `api.endpoints.get_posts_with_comments`.
    min_chars:
        Filtra posts com body de comprimento < min_chars.
    min_posts:
        Limiar para classificar o usuário como "ativo".
        Baseado no total real de posts, não no filtrado.

    Retorno
    -------
    UserMetrics com todas as métricas calculadas.

    Exemplos
    --------
    >>> posts = [
    ...     {"id": 1, "body": "hello world", "_comment_count": 3},
    ...     {"id": 2, "body": "hi",           "_comment_count": 1},
    ... ]
    >>> m = compute_metrics(posts, min_chars=5, min_posts=1)
    >>> m.total_posts
    1
    >>> m.avg_chars
    11.0
    >>> m.is_active
    True
    """
    raw_total = len(posts)

    # Filtro por mínimo de caracteres (sobre o body do post)
    filtered = [p for p in posts if len(p.get("body", "")) >= min_chars]
    total_posts = len(filtered)

    avg_chars = (
        sum(len(p.get("body", "")) for p in filtered) / total_posts
        if total_posts > 0 else 0.0
    )

    avg_comments = (
        sum(p.get("_comment_count", 0) for p in filtered) / total_posts
        if total_posts > 0 else 0.0
    )

    # Status baseado no total real (sem filtro), conforme spec do case
    is_active = raw_total >= min_posts

    return UserMetrics(
        raw_total=raw_total,
        filtered_posts=filtered,
        total_posts=total_posts,
        avg_chars=round(avg_chars, 2),
        avg_comments=round(avg_comments, 2),
        is_active=is_active,
        min_chars_threshold=min_chars,
        min_posts_threshold=min_posts,
    )
