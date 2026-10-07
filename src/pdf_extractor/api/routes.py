"""Endpoints HTTP del servicio.

El handler de ``/extract`` solo coordina: lee el upload, pide un lugar al
control de admisión y delega la extracción al pool de procesos. No hace
trabajo pesado propio, así el event loop queda libre para atender más
conexiones mientras los workers extraen.
"""

from __future__ import annotations

import time

import orjson
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route

from ..concurrency import AdmissionController, WorkerPool
from ..worker_tasks import extract_to_json
from .uploads import read_pdf_upload


class Endpoints:
    def __init__(
        self,
        pool: WorkerPool,
        admission: AdmissionController,
        max_upload_bytes: int,
        upload_timeout_seconds: float,
    ) -> None:
        self._pool = pool
        self._admission = admission
        self._max_upload_bytes = max_upload_bytes
        self._upload_timeout_seconds = upload_timeout_seconds

    def routes(self) -> list[Route]:
        return [
            Route("/extract", self.extract, methods=["POST"]),
            Route("/health", self.health, methods=["GET"]),
        ]

    async def extract(self, request: Request) -> Response:
        """POST /extract: recibe un PDF y devuelve ``{"content", "page_count"}``."""
        pdf = await read_pdf_upload(request, self._max_upload_bytes, self._upload_timeout_seconds)

        async with self._admission.slot() as queued_seconds:
            started = time.perf_counter()
            result = await self._pool.run(extract_to_json, pdf)
            extract_seconds = time.perf_counter() - started

        queue_ms, extract_ms = queued_seconds * 1000, extract_seconds * 1000
        request.state.log_fields = {
            "pdf_bytes": len(pdf),
            "page_count": result.page_count,
            "queue_ms": round(queue_ms, 1),
            "extract_ms": round(extract_ms, 1),
        }
        # Server-Timing es un encabezado estándar (W3C) para informar en qué
        # se fue el tiempo del lado del servidor: sirve para separar espera en
        # cola de procesamiento al analizar las pruebas de carga.
        headers = {"Server-Timing": f"queue;dur={queue_ms:.1f}, extract;dur={extract_ms:.1f}"}
        return Response(result.body, media_type="application/json", headers=headers)

    async def health(self, _: Request) -> Response:
        """GET /health: lo usa el balanceador para saber si la réplica está viva."""
        status = {"status": "ok", "running": self._admission.running, "waiting": self._admission.waiting}
        return Response(orjson.dumps(status), media_type="application/json")
