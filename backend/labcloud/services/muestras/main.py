"""Servicio de Muestras (Nodo 4 - Datos maestros, puerto 8006).

Responsabilidad: registrar las muestras recibidas y administrar su estado.
El Mediator del Servicio de Solicitudes lo consulta para validar la muestra y
lo actualiza a medida que el análisis avanza.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from labcloud.services.muestras.models import Muestra
from labcloud.services.muestras.schemas import MuestraCrear, MuestraEstado, MuestraSalida
from labcloud.shared.db import Database
from labcloud.shared.service import crear_app

log = logging.getLogger("labcloud.muestras")
db = Database("muestras")


def _inicializar() -> None:
    db.crear_tablas()


app: FastAPI = crear_app("muestras", al_iniciar=_inicializar)
Sesion = Annotated[Session, Depends(db.dependencia)]


@app.post(
    "/muestras",
    response_model=MuestraSalida,
    status_code=status.HTTP_201_CREATED,
    tags=["muestras"],
)
def registrar_muestra(datos: MuestraCrear, session: Sesion) -> Muestra:
    if session.scalar(select(Muestra).where(Muestra.codigo == datos.codigo)):
        raise HTTPException(status.HTTP_409_CONFLICT, "El código de muestra ya existe")
    muestra = Muestra(**datos.model_dump())
    session.add(muestra)
    session.flush()
    log.info("Muestra registrada: %s (%s)", muestra.codigo, muestra.tipo)
    return muestra


@app.get("/muestras", response_model=list[MuestraSalida], tags=["muestras"])
def listar_muestras(
    session: Sesion,
    cliente_id: str | None = None,
    estado: str | None = None,
    limite: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[Muestra]:
    consulta = select(Muestra).order_by(Muestra.recibida_en.desc())
    if cliente_id:
        consulta = consulta.where(Muestra.cliente_id == cliente_id)
    if estado:
        consulta = consulta.where(Muestra.estado == estado)
    return list(session.scalars(consulta.limit(limite)))


@app.get("/muestras/{muestra_id}", response_model=MuestraSalida, tags=["muestras"])
def obtener_muestra(muestra_id: str, session: Sesion) -> Muestra:
    muestra = session.get(Muestra, muestra_id)
    if not muestra:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Muestra no encontrada")
    return muestra


@app.patch("/muestras/{muestra_id}/estado", response_model=MuestraSalida, tags=["muestras"])
def actualizar_estado(muestra_id: str, datos: MuestraEstado, session: Sesion) -> Muestra:
    """Cambia el estado de la muestra. Invocado por el Mediator durante el análisis."""
    muestra = session.get(Muestra, muestra_id)
    if not muestra:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Muestra no encontrada")
    anterior = muestra.estado
    muestra.estado = datos.estado
    session.flush()
    log.info("Muestra %s: %s -> %s", muestra.codigo, anterior, muestra.estado)
    return muestra
