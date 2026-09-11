"""Registro de eventos con identificación de servicio, nodo, proceso e hilo.

La traza incluye el hilo que atiende cada operación porque es la evidencia
principal del procesamiento concurrente exigido por el diseño (RF03, RNF01).
"""

from __future__ import annotations

import logging
import os
import sys

_FORMATO = (
    "%(asctime)s | %(nodo)-7s | %(servicio)-14s | pid=%(process)-6d | "
    "hilo=%(threadName)-22s | %(levelname)-7s | %(message)s"
)


class _ContextoServicio(logging.Filter):
    def __init__(self, servicio: str, nodo: str) -> None:
        super().__init__()
        self.servicio = servicio
        self.nodo = nodo

    def filter(self, record: logging.LogRecord) -> bool:
        record.servicio = self.servicio
        record.nodo = self.nodo
        return True


def configurar_logging(servicio: str, nodo: str) -> logging.Logger:
    """Configura el logging del proceso y devuelve el logger del servicio."""
    nivel = os.getenv("LABCLOUD_LOG_LEVEL", "INFO").upper()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_FORMATO, datefmt="%H:%M:%S"))
    handler.addFilter(_ContextoServicio(servicio, nodo))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(nivel)

    # Uvicorn trae sus propios handlers; se delegan al raíz para unificar el formato.
    for nombre in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        log = logging.getLogger(nombre)
        log.handlers.clear()
        log.propagate = True

    logging.getLogger("httpx").setLevel(logging.WARNING)
    return logging.getLogger(f"labcloud.{servicio}")
