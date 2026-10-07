"""Configuración del servicio leída de variables de entorno (Twelve-Factor, III).

Toda la configuración entra por el entorno: la misma imagen Docker sirve para
desarrollo, pruebas de carga y el benchmark, cambiando solo variables. Si un
valor es inválido el servicio no arranca (falla rápido y con un mensaje claro)
en lugar de correr con una configuración que nadie pidió.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from dataclasses import dataclass

_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR"})


class ConfigError(ValueError):
    """Una variable de entorno tiene un valor inválido."""


@dataclass(frozen=True, slots=True)
class Settings:
    # Port binding (Twelve-Factor, VII): el servicio se expone solo, sin un
    # servidor web delante dentro del contenedor.
    host: str = "0.0.0.0"
    port: int = 8000

    # Procesos que extraen PDFs en paralelo dentro de la réplica. Con el
    # límite de 1 CPU por contenedor, más de un proceso solo se reparte el
    # mismo núcleo, así que el valor por defecto es 1.
    extraction_workers: int = 1

    # Backpressure: cuántos pedidos pueden esperar un worker libre dentro de
    # la réplica y cuánto tiempo como máximo. Pasado ese tiempo el pedido ya
    # no es útil (el cliente de Vegeta corta a los 30 s) y se responde 503.
    max_queue_size: int = 8
    queue_timeout_seconds: float = 25.0

    # Tamaño máximo del PDF. Acota la memoria: cada pedido en cola guarda su
    # PDF completo hasta que lo procesa un worker.
    max_upload_mb: int = 32

    # Tiempo máximo para recibir el archivo completo. Un cliente que lo manda
    # de a gotas bloquearía la réplica, que atiende un pedido por vez.
    upload_timeout_seconds: float = 15.0

    log_level: str = "INFO"

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @classmethod
    def from_env(cls, environ: Mapping[str, str] = os.environ) -> Settings:
        """Crea la configuración a partir de las variables de entorno.

        Raises:
            ConfigError: si alguna variable tiene un valor inválido.
        """
        # Con slots=True los atributos de clase no guardan los valores por
        # defecto, así que se leen de una instancia creada sin argumentos.
        defaults = cls()
        log_level = environ.get("LOG_LEVEL", defaults.log_level).upper()
        if log_level not in _LOG_LEVELS:
            raise ConfigError(f"LOG_LEVEL debe ser uno de {sorted(_LOG_LEVELS)}, no {log_level!r}")

        return cls(
            host=environ.get("HOST", defaults.host),
            port=_read_int(environ, "PORT", defaults.port, minimum=1, maximum=65_535),
            extraction_workers=_read_int(environ, "EXTRACTION_WORKERS", defaults.extraction_workers, minimum=1),
            max_queue_size=_read_int(environ, "MAX_QUEUE_SIZE", defaults.max_queue_size, minimum=0),
            queue_timeout_seconds=_read_float(environ, "QUEUE_TIMEOUT_SECONDS", defaults.queue_timeout_seconds),
            max_upload_mb=_read_int(environ, "MAX_UPLOAD_MB", defaults.max_upload_mb, minimum=1),
            upload_timeout_seconds=_read_float(environ, "UPLOAD_TIMEOUT_SECONDS", defaults.upload_timeout_seconds),
            log_level=log_level,
        )


def _read_int(environ: Mapping[str, str], name: str, default: int, *, minimum: int, maximum: int | None = None) -> int:
    raw = environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} debe ser un número entero, no {raw!r}") from None
    if value < minimum or (maximum is not None and value > maximum):
        limit = f"entre {minimum} y {maximum}" if maximum is not None else f"mayor o igual a {minimum}"
        raise ConfigError(f"{name} debe ser {limit}, no {value}")
    return value


def _read_float(environ: Mapping[str, str], name: str, default: float) -> float:
    raw = environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} debe ser un número, no {raw!r}") from None
    if not math.isfinite(value) or value <= 0:
        raise ConfigError(f"{name} debe ser un número mayor a 0, no {raw!r}")
    return value
