"""
main.py
-------
Entrypoint da aplicação User Analytics.

Inicia o servidor Flask com as configurações definidas em config.py.
"""

from __future__ import annotations

import config
from ui.interface import app

if __name__ == "__main__":
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
    )
