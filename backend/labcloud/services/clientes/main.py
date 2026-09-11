"""Servicio de Clientes (Nodo 4 - Datos maestros, puerto 8005).

Responsabilidad: registrar y consultar la información de los clientes del
laboratorio. El Servicio de Solicitudes lo consulta —a través del Mediator—
para validar que el cliente exista antes de aceptar una solicitud de análisis.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from labcloud.services.clientes.models import Cliente
from labcloud.services.clientes.schemas import ClienteCrear, ClienteSalida
from labcloud.shared.db import Database
from labcloud.shared.service import crear_app

log = logging.getLogger("labcloud.clientes")
db = Database("clientes")

CLIENTES_DEMO = [
    ("CC-1032456789", "Laura Gómez Pérez", "laura.gomez@correo.co", "3105557788", "Bogotá"),
    ("NIT-900123456", "Clínica San Rafael", "contacto@sanrafael.co", "6012223344", "Bogotá"),
    ("CC-1098765432", "Andrés Molina Ruiz", "andres.molina@correo.co", "3129998877", "Medellín"),
    ("NIT-901556677", "IPS Salud Total", "laboratorio@saludtotal.co", "6044445566", "Cali"),
]


def _inicializar() -> None:
    db.crear_tablas()
    with db.sesion() as session:
        if session.scalar(select(Cliente).limit(1)):
            return
        for documento, nombre, email, telefono, ciudad in CLIENTES_DEMO:
            session.add(
                Cliente(
                    documento=documento,
                    nombre=nombre,
                    email=email,
                    telefono=telefono,
                    ciudad=ciudad,
                )
            )
        log.info("Clientes de demostración creados (%d)", len(CLIENTES_DEMO))


app: FastAPI = crear_app("clientes", al_iniciar=_inicializar)
Sesion = Annotated[Session, Depends(db.dependencia)]


@app.post(
    "/clientes",
    response_model=ClienteSalida,
    status_code=status.HTTP_201_CREATED,
    tags=["clientes"],
)
def crear_cliente(datos: ClienteCrear, session: Sesion) -> Cliente:
    if session.scalar(select(Cliente).where(Cliente.documento == datos.documento)):
        raise HTTPException(status.HTTP_409_CONFLICT, "El documento ya está registrado")
    cliente = Cliente(**{**datos.model_dump(), "email": str(datos.email)})
    session.add(cliente)
    session.flush()
    log.info("Cliente registrado: %s (%s)", cliente.nombre, cliente.documento)
    return cliente


@app.get("/clientes", response_model=list[ClienteSalida], tags=["clientes"])
def listar_clientes(
    session: Sesion,
    buscar: str | None = None,
    limite: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[Cliente]:
    consulta = select(Cliente).order_by(Cliente.creado_en.desc()).limit(limite)
    if buscar:
        patron = f"%{buscar}%"
        consulta = select(Cliente).where(
            Cliente.nombre.ilike(patron) | Cliente.documento.ilike(patron)
        ).limit(limite)
    return list(session.scalars(consulta))


@app.get("/clientes/{cliente_id}", response_model=ClienteSalida, tags=["clientes"])
def obtener_cliente(cliente_id: str, session: Sesion) -> Cliente:
    cliente = session.get(Cliente, cliente_id)
    if not cliente:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente no encontrado")
    return cliente
