"""Armado de la aplicación: conecta configuración, concurrencia y endpoints."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.middleware import Middleware

from . import __version__
from .api.access_log import AccessLogMiddleware
from .api.errors import EXCEPTION_HANDLERS
from .api.routes import Endpoints
from .concurrency import AdmissionController, WorkerPool
from .config import Settings
from .worker_tasks import init_worker

logger = logging.getLogger(__name__)


def create_app(settings: Settings) -> Starlette:
    pool = WorkerPool(size=settings.extraction_workers, initializer=init_worker)
    admission = AdmissionController(
        max_concurrent=settings.extraction_workers,
        max_waiting=settings.max_queue_size,
        wait_timeout=settings.queue_timeout_seconds,
    )
    endpoints = Endpoints(pool, admission, settings.max_upload_bytes, settings.upload_timeout_seconds)

    @asynccontextmanager
    async def lifespan(_: Starlette) -> AsyncIterator[None]:
        # Los workers arrancan antes de aceptar tráfico y se apagan después de
        # terminar los pedidos en curso (Twelve-Factor, IX: desechabilidad).
        await pool.start()
        logger.info("Servicio listo", extra={"fields": {"version": __version__, **_public_settings(settings)}})
        yield
        logger.info("Apagando: se esperan los pedidos en curso")
        pool.close()

    return Starlette(
        routes=endpoints.routes(),
        middleware=[Middleware(AccessLogMiddleware)],
        exception_handlers=EXCEPTION_HANDLERS,
        lifespan=lifespan,
    )


def _public_settings(settings: Settings) -> dict[str, object]:
    return {
        "port": settings.port,
        "extraction_workers": settings.extraction_workers,
        "max_queue_size": settings.max_queue_size,
        "queue_timeout_seconds": settings.queue_timeout_seconds,
        "max_upload_mb": settings.max_upload_mb,
        "upload_timeout_seconds": settings.upload_timeout_seconds,
    }
