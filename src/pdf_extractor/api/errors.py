"""Errores de la API y su formato de respuesta.

Todas las respuestas de error tienen la misma forma, para que un cliente (o
un script de pruebas) las pueda interpretar sin casos especiales::

    {"error": {"code": "SERVICE_OVERLOADED", "message": "..."}}

| Código HTTP | ``code``                 | Cuándo                                        |
|-------------|--------------------------|-----------------------------------------------|
| 400         | ``EMPTY_BODY``           | El pedido no trae contenido                   |
| 400         | ``INVALID_MULTIPART``    | El multipart está mal formado o no trae archivo |
| 408         | ``REQUEST_TIMEOUT``      | El archivo no llegó en ``UPLOAD_TIMEOUT_SECONDS`` |
| 413         | ``PAYLOAD_TOO_LARGE``    | El PDF supera ``MAX_UPLOAD_MB``               |
| 422         | ``INVALID_PDF``          | No es un PDF, está dañado o tiene contraseña  |
| 499         | ``CLIENT_DISCONNECTED``  | El cliente cortó antes de enviar todo (solo log) |
| 500         | ``WORKER_CRASHED``       | El proceso de extracción murió                |
| 500         | ``INTERNAL_ERROR``       | Error inesperado                              |
| 503         | ``SERVICE_OVERLOADED``   | Backpressure: cola llena o espera vencida     |
"""

from __future__ import annotations

import orjson
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.responses import Response

from ..concurrency import OverloadedError, WorkerCrashedError
from ..extraction import InvalidPdfError

# Segundos que sugerimos esperar antes de reintentar cuando hay saturación.
# Es corto a propósito: las colas se vacían en pocos segundos.
RETRY_AFTER_SECONDS = 2


class ApiError(Exception):
    """Error de validación del pedido, con su código HTTP y su código estable."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def error_response(status: int, code: str, message: str, headers: dict[str, str] | None = None) -> Response:
    body = orjson.dumps({"error": {"code": code, "message": message}})
    return Response(body, status_code=status, media_type="application/json", headers=headers)


async def _api_error(_: Request, error: Exception) -> Response:
    assert isinstance(error, ApiError)
    return error_response(error.status, error.code, error.message)


async def _invalid_pdf(_: Request, error: Exception) -> Response:
    return error_response(422, "INVALID_PDF", str(error))


async def _overloaded(_: Request, error: Exception) -> Response:
    headers = {"Retry-After": str(RETRY_AFTER_SECONDS)}
    return error_response(503, "SERVICE_OVERLOADED", str(error), headers)


async def _worker_crashed(_: Request, error: Exception) -> Response:
    return error_response(500, "WORKER_CRASHED", str(error))


async def _http_exception(_: Request, error: Exception) -> Response:
    # Errores que genera Starlette solo (404 ruta inexistente, 405 método no
    # permitido): les damos el mismo formato JSON que al resto.
    assert isinstance(error, HTTPException)
    # Se conservan sus encabezados (por ejemplo, Allow en un 405).
    return error_response(error.status_code, "HTTP_ERROR", error.detail, dict(error.headers or {}))


async def _unexpected(_: Request, error: Exception) -> Response:
    # No lo registramos acá: Starlette vuelve a lanzar la excepción después
    # de responder y uvicorn la escribe en el log con su traceback completo.
    # Al cliente nunca le exponemos detalles internos.
    return error_response(500, "INTERNAL_ERROR", "Error interno del servidor.")


EXCEPTION_HANDLERS = {
    ApiError: _api_error,
    InvalidPdfError: _invalid_pdf,
    OverloadedError: _overloaded,
    WorkerCrashedError: _worker_crashed,
    HTTPException: _http_exception,
    Exception: _unexpected,
}
