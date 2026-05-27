"""
export/report_sender.py
-----------------------
Simulação do envio do relatório via POST para /reports.
"""

from __future__ import annotations

from typing import Any

from api.client import HttpClient
from api.endpoints import post_report


async def send_report(
    client: HttpClient,
    row: dict[str, Any],
) -> dict[str, Any]:
    """Envia o payload do relatório via POST e retorna a resposta da API.

    Parâmetros
    ----------
    client:
        Instância de HttpClient compartilhada com o restante da aplicação.
    row:
        Dicionário com os dados do relatório (build_report_row).

    Retorno
    -------
    Resposta JSON da API (contém `id` gerado pelo servidor mock).
    """
    response = await post_report(client, row)
    return response
