"""Fábrica común de aplicaciones FastAPI para los servicios de LabCloud.

Unifica lo que todo proceso del sistema necesita: CORS para el frontend,
configuración de logging con identificación de nodo/hilo y los endpoints de
observabilidad ``/health`` e ``/info`` que consume el panel de control.
"""

from __future__ import annotations

import inspect
import os
import threading
import time
from collections.abc import Callable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from labcloud import __version__
from labcloud.shared.config import CORS_ORIGINS, NODOS, servicio
from labcloud.shared.logging_conf import configurar_logging
from labcloud.shared.schemas import SaludServicio

ARRANQUE = time.time()


async def _invocar(funcion: Callable[[], Any]) -> None:
    """Ejecuta el gancho de ciclo de vida, sea síncrono o asíncrono."""
    resultado = funcion()
    if inspect.isawaitable(resultado):
        await resultado


def crear_app(
    service_id: str,
    *,
    al_iniciar: Callable[[], Any] | None = None,
    al_detener: Callable[[], Any] | None = None,
    tags_extra: list[dict[str, str]] | None = None,
) -> FastAPI:
    spec = servicio(service_id)
    nodo = NODOS[spec.nodo]
    log = configurar_logging(spec.id, spec.nodo)

    @asynccontextmanager
    async def ciclo_de_vida(_app: FastAPI):
        log.info("=" * 78)
        log.info("Iniciando %s", spec.nombre)
        log.info("Nodo lógico : %s", nodo.nombre)
        log.info("Proceso     : pid=%s  puerto=%s", os.getpid(), spec.puerto)
        if spec.patrones:
            log.info("Patrones    : %s", ", ".join(spec.patrones))
        log.info("=" * 78)
        if al_iniciar:
            await _invocar(al_iniciar)
        yield
        if al_detener:
            await _invocar(al_detener)
        log.info("%s detenido", spec.nombre)

    app = FastAPI(
        title=f"LabCloud Distributed - {spec.nombre}",
        description=spec.descripcion,
        version=__version__,
        lifespan=ciclo_de_vida,
        openapi_tags=tags_extra,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.spec = spec
    app.state.nodo = nodo

    @app.get("/health", response_model=SaludServicio, tags=["observabilidad"])
    def health() -> SaludServicio:
        """Estado del proceso. Lo consulta el Gateway y el panel de nodos."""
        return SaludServicio(
            servicio=spec.id,
            nombre=spec.nombre,
            nodo=nodo.id,
            nodo_nombre=nodo.nombre,
            puerto=spec.puerto,
            pid=os.getpid(),
            hilos_activos=threading.active_count(),
            version=__version__,
            uptime_segundos=round(time.time() - ARRANQUE, 2),
            patrones=list(spec.patrones),
        )

    @app.get("/info", tags=["observabilidad"])
    def info() -> dict:
        """Ficha descriptiva del componente dentro de la arquitectura."""
        return {
            "servicio": spec.id,
            "nombre": spec.nombre,
            "descripcion": spec.descripcion,
            "nodo": {
                "id": nodo.id,
                "nombre": nodo.nombre,
                "responsabilidad": nodo.responsabilidad,
            },
            "puerto": spec.puerto,
            "pid": os.getpid(),
            "patrones": list(spec.patrones),
            "hilos": [h.name for h in threading.enumerate()],
        }

    return app
