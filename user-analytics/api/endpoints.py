"""
api/endpoints.py
----------------
Funções de domínio que encapsulam cada rota da API.

Separa o "o quê buscar" (domínio) do "como buscar" (HttpClient),
seguindo o mesmo princípio do pipeline que separa load_data()
do modelo LSTM — cada camada conhece apenas a imediatamente abaixo.
"""

from __future__ import annotations

import asyncio
from typing import Any

from api.client import HttpClient


# =============================================================================
# Tipos de retorno (TypeAlias para legibilidade)
# =============================================================================

User    = dict[str, Any]
Post    = dict[str, Any]
Comment = dict[str, Any]


# =============================================================================
# Funções de domínio
# =============================================================================

async def get_users(client: HttpClient) -> list[User]:
    """Retorna a lista completa de usuários."""
    return await client.get("/users")


async def get_posts_by_user(client: HttpClient, user_id: int) -> list[Post]:
    """Retorna todos os posts de um usuário."""
    return await client.get(f"/posts?userId={user_id}")


async def get_comments_by_post(client: HttpClient, post_id: int) -> list[Comment]:
    """Retorna todos os comentários de um post."""
    return await client.get(f"/comments?postId={post_id}")


async def get_posts_with_comments(
    client: HttpClient,
    user_id: int,
) -> list[Post]:
    """Busca posts do usuário e enriquece cada um com _comment_count.

    Os comentários de todos os posts são buscados em paralelo via
    asyncio.gather — reduz o tempo total de N requisições sequenciais
    para o tempo da requisição mais lenta.

    Parâmetros
    ----------
    client:
        Instância de HttpClient já configurada.
    user_id:
        ID do usuário cujos posts serão buscados.

    Retorno
    -------
    Lista de posts com campo extra `_comment_count: int`.
    """
    posts = await get_posts_by_user(client, user_id)

    if not posts:
        return []

    # Busca paralela de comentários
    comment_lists: list[list[Comment]] = await asyncio.gather(
        *[get_comments_by_post(client, post["id"]) for post in posts]
    )

    enriched: list[Post] = []
    for post, comments in zip(posts, comment_lists):
        enriched.append({**post, "_comment_count": len(comments)})

    return enriched


async def post_report(
    client: HttpClient,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Simula o envio do relatório via POST para /posts (proxy de /reports).

    A API jsonplaceholder não possui /reports, mas aceita POST em /posts
    e devolve o payload com um id gerado — comportamento idêntico ao esperado.
    """
    return await client.post("/posts", payload)
