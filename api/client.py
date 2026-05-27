"""
api/client.py
-------------
Cliente HTTP assíncrono com:
  - Cache em memória com TTL por chave
  - Retry automático com backoff exponencial
  - Tratamento centralizado de erros HTTP
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from typing import Any

import aiohttp

import config


# =============================================================================
# Cache em memória com TTL
# =============================================================================

@dataclass
class _CacheEntry:
    value: Any
    created_at: float = field(default_factory=time.monotonic)

    def is_expired(self, ttl: int) -> bool:
        return (time.monotonic() - self.created_at) > ttl


class MemoryCache:
    """Cache em memória com expiração por TTL.

    Cada chave armazena o valor e o timestamp de inserção.
    Entradas expiradas são descartadas na leitura.
    """

    def __init__(self, ttl: int = config.CACHE_TTL_SECONDS) -> None:
        self._store: dict[str, _CacheEntry] = {}
        self._ttl = ttl

    def get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is None:
            return None
        if entry.is_expired(self._ttl):
            del self._store[key]
            return None
        return entry.value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = _CacheEntry(value=value)

    def has(self, key: str) -> bool:
        return self.get(key) is not None

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        # Conta apenas entradas ainda válidas
        return sum(
            1 for e in self._store.values()
            if not e.is_expired(self._ttl)
        )


# =============================================================================
# Exceções customizadas
# =============================================================================

class ApiError(Exception):
    """Erro genérico de comunicação com a API."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class NotFoundError(ApiError):
    """Recurso não encontrado (HTTP 404)."""


class ServerError(ApiError):
    """Erro interno do servidor (HTTP 5xx)."""


# =============================================================================
# Cliente HTTP
# =============================================================================

class HttpClient:
    """Wrapper assíncrono sobre aiohttp com cache e retry.

    Parâmetros
    ----------
    base_url:
        URL base da API (sem barra final).
    cache:
        Instância de MemoryCache. Se None, cria uma nova.
    max_retries:
        Número de tentativas em falhas transitórias (5xx / timeout).
    backoff:
        Tempo base (segundos) entre tentativas — dobra a cada retry.
    timeout:
        Timeout em segundos por requisição.
    """

    def __init__(
        self,
        base_url: str = config.BASE_URL,
        cache: MemoryCache | None = None,
        max_retries: int = config.MAX_RETRIES,
        backoff: float = config.RETRY_BACKOFF,
        timeout: int = config.REQUEST_TIMEOUT,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._cache = cache or MemoryCache()
        self._max_retries = max_retries
        self._backoff = backoff
        self._timeout = aiohttp.ClientTimeout(total=timeout)

    # ------------------------------------------------------------------
    # Interface pública
    # ------------------------------------------------------------------

    async def get(self, path: str) -> Any:
        """GET com cache. Retorna o JSON deserializado."""
        url = f"{self._base_url}{path}"

        cached = self._cache.get(url)
        if cached is not None:
            return cached

        data = await self._request_with_retry("GET", url)
        self._cache.set(url, data)
        return data

    async def post(self, path: str, payload: dict[str, Any]) -> Any:
        """POST sem cache. Retorna o JSON da resposta."""
        url = f"{self._base_url}{path}"
        return await self._request_with_retry("POST", url, json=payload)

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> Any:
        """Executa a requisição com retry e backoff exponencial.

        Só tenta novamente em erros transitórios (5xx, timeout, conexão).
        Erros 4xx são propagados imediatamente.
        """
        last_exc: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                async with aiohttp.ClientSession(timeout=self._timeout) as session:
                    async with session.request(method, url, **kwargs) as resp:
                        return await self._handle_response(resp)

            except (ApiError,) as exc:
                # Erros 4xx não são transitórios — propaga imediatamente
                if exc.status_code and 400 <= exc.status_code < 500:
                    raise
                last_exc = exc

            except (aiohttp.ClientConnectionError, asyncio.TimeoutError) as exc:
                last_exc = ApiError(f"Falha de conexão: {exc}")

            if attempt < self._max_retries:
                wait = self._backoff * (2 ** (attempt - 1))
                await asyncio.sleep(wait)

        raise last_exc or ApiError("Falha desconhecida após retries.")

    @staticmethod
    async def _handle_response(resp: aiohttp.ClientResponse) -> Any:
        """Mapeia status HTTP para exceções semânticas."""
        if resp.status == 404:
            raise NotFoundError(f"Recurso não encontrado: {resp.url}", status_code=404)
        if resp.status >= 500:
            raise ServerError(f"Erro no servidor: HTTP {resp.status}", status_code=resp.status)
        if not resp.ok:
            raise ApiError(f"Erro HTTP {resp.status}: {resp.url}", status_code=resp.status)

        return await resp.json()
