"""
config.py
---------
Centraliza todas as constantes e configurações da aplicação.
Única fonte de verdade para parâmetros globais.
"""

from __future__ import annotations

# =============================================================================
# API
# =============================================================================

BASE_URL: str = "https://jsonplaceholder.typicode.com"

# Timeout em segundos para requisições HTTP
REQUEST_TIMEOUT: int = 10

# Número máximo de tentativas em caso de falha transitória
MAX_RETRIES: int = 3

# Intervalo base (segundos) entre tentativas — dobra a cada retry (backoff exponencial)
RETRY_BACKOFF: float = 0.5

# =============================================================================
# CACHE
# =============================================================================

# TTL do cache em memória (segundos)
CACHE_TTL_SECONDS: int = 300  # 5 minutos

# =============================================================================
# ANALYTICS
# =============================================================================

# Valor padrão para mínimo de caracteres ao iniciar
DEFAULT_MIN_CHARS: int = 0

# Valor padrão para mínimo de posts que define usuário "ativo"
DEFAULT_MIN_POSTS: int = 5

# =============================================================================
# EXPORT
# =============================================================================

# Nome base dos arquivos gerados (sem extensão)
EXPORT_FILENAME_BASE: str = "relatorio_usuarios"

# Colunas e ordem do relatório exportado
REPORT_COLUMNS: list[str] = [
    "id_usuario",
    "nome",
    "qtd_posts",
    "media_chars",
    "media_comentarios",
    "status",
]

# =============================================================================
# FLASK
# =============================================================================

FLASK_HOST: str = "127.0.0.1"
FLASK_PORT: int = 5000
FLASK_DEBUG: bool = True
