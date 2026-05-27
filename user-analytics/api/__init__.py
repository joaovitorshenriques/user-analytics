"""api — camada de comunicação com a API externa."""
from api.client import HttpClient, MemoryCache, ApiError, NotFoundError, ServerError
from api.endpoints import get_users, get_posts_with_comments, post_report

__all__ = [
    "HttpClient",
    "MemoryCache",
    "ApiError",
    "NotFoundError",
    "ServerError",
    "get_users",
    "get_posts_with_comments",
    "post_report",
]
