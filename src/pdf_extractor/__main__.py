"""Punto de entrada: ``python -m pdf_extractor``.

Lee la configuración del entorno, configura los logs y levanta uvicorn con
un único proceso de event loop (el paralelismo lo dan los workers del pool).
"""

from __future__ import annotations

import sys

import uvicorn

from .app import create_app
from .config import ConfigError, Settings
from .logs import configure_logging


def main() -> None:
    try:
        settings = Settings.from_env()
    except ConfigError as error:
        sys.exit(f"Configuración inválida: {error}")

    configure_logging(settings.log_level)
    uvicorn.run(
        create_app(settings),
        host=settings.host,
        port=settings.port,
        log_config=None,  # usamos nuestra configuración de logs (JSON)
        access_log=False,  # el log de acceso lo escribe AccessLogMiddleware
        server_header=False,
        # Tope de conexiones simultáneas: lo que se procesa + lo que puede
        # esperar + margen para health checks y uploads en curso. Acota la
        # memoria aunque alguien le pegue directo a la réplica, sin proxy.
        limit_concurrency=settings.extraction_workers + settings.max_queue_size + 8,
    )


if __name__ == "__main__":
    main()
