"""Servicio de Resultados (Nodo 3 - Servicios de soporte, puerto 8002).

Rol en la arquitectura: **sujeto** del patrón Observer distribuido. Registra el
resultado de un análisis y publica el evento ``resultado.disponible``.

La publicación es asíncrona: el resultado se confirma al Servicio de Solicitudes
apenas queda persistido, sin esperar a que el Servicio de Notificaciones
responda. Así, una caída del observador no interrumpe el flujo principal
(sección 8.4.3 del diseño).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from labcloud.services.resultados.models import EventoPublicado, Resultado
from labcloud.services.resultados.schemas import ResultadoCrear, ResultadoSalida
from labcloud.shared.db import Database
from labcloud.shared.events import PublicadorEventos
from labcloud.shared.schemas import Evento, SolicitudSuscripcion, Suscripcion
from labcloud.shared.service import crear_app

log = logging.getLogger("labcloud.resultados")
db = Database("resultados")

#: Sujeto observable: mantiene el registro de observadores y despacha eventos.
publicador = PublicadorEventos("resultados", despachadores=2)

TIPO_EVENTO = "resultado.disponible"


def _persistir_evento(evento: Evento) -> None:
    """Guarda cada evento publicado como evidencia de funcionamiento."""
    with db.sesion() as session:
        session.add(
            EventoPublicado(
                id=evento.id,
                tipo=evento.tipo,
                origen=evento.origen,
                datos=evento.datos,
                publicado_en=evento.ocurrido_en,
            )
        )


def _inicializar() -> None:
    db.crear_tablas()
    publicador.al_publicar = _persistir_evento
    publicador.iniciar()


def _detener() -> None:
    publicador.detener()


app: FastAPI = crear_app("resultados", al_iniciar=_inicializar, al_detener=_detener)
Sesion = Annotated[Session, Depends(db.dependencia)]


# --- Registro y consulta de resultados --------------------------------------


@app.post(
    "/resultados",
    response_model=ResultadoSalida,
    status_code=status.HTTP_201_CREATED,
    tags=["resultados"],
)
def registrar_resultado(datos: ResultadoCrear, session: Sesion) -> Resultado:
    """Registra el resultado y publica el evento correspondiente.

    El orden importa: primero se confirma la persistencia y después se publica.
    El ``commit`` explícito libera el bloqueo de escritura de SQLite antes de
    que la bitácora de eventos abra su propia transacción, y garantiza que el
    evento solo se emita sobre un resultado ya almacenado.
    ``publicar()`` únicamente encola, por lo que esta operación responde de
    inmediato aunque el Servicio de Notificaciones esté caído.
    """
    resultado = Resultado(**datos.model_dump())
    session.add(resultado)
    session.commit()
    log.info(
        "Resultado registrado para la solicitud %s (%s)",
        resultado.codigo_solicitud or resultado.solicitud_id[:8],
        resultado.diagnostico or "sin diagnóstico",
    )

    publicador.publicar(
        TIPO_EVENTO,
        {
            "resultado_id": resultado.id,
            "solicitud_id": resultado.solicitud_id,
            "codigo_solicitud": resultado.codigo_solicitud,
            "cliente_id": resultado.cliente_id,
            "cliente_nombre": resultado.cliente_nombre,
            "cliente_email": resultado.cliente_email,
            "muestra_id": resultado.muestra_id,
            "codigo_muestra": resultado.codigo_muestra,
            "tipo_analisis": resultado.tipo_analisis,
            "diagnostico": resultado.diagnostico,
        },
    )
    return resultado


@app.get("/resultados", response_model=list[ResultadoSalida], tags=["resultados"])
def listar_resultados(
    session: Sesion,
    solicitud_id: str | None = None,
    limite: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[Resultado]:
    consulta = select(Resultado).order_by(Resultado.registrado_en.desc())
    if solicitud_id:
        consulta = consulta.where(Resultado.solicitud_id == solicitud_id)
    return list(session.scalars(consulta.limit(limite)))


@app.get("/resultados/resumen", tags=["resultados"])
def resumen(session: Sesion) -> dict:
    total = session.scalar(select(func.count(Resultado.id))) or 0
    promedio = session.scalar(select(func.avg(Resultado.duracion_ms))) or 0.0
    por_tipo = session.execute(
        select(Resultado.tipo_analisis, func.count(Resultado.id)).group_by(
            Resultado.tipo_analisis
        )
    ).all()
    return {
        "total": total,
        "duracion_promedio_ms": round(float(promedio), 2),
        "por_tipo_analisis": {tipo: cantidad for tipo, cantidad in por_tipo},
        "eventos": publicador.estado(),
    }


@app.get("/resultados/{resultado_id}", response_model=ResultadoSalida, tags=["resultados"])
def obtener_resultado(resultado_id: str, session: Sesion) -> Resultado:
    resultado = session.get(Resultado, resultado_id)
    if not resultado:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Resultado no encontrado")
    return resultado


# --- Observer distribuido: registro de observadores -------------------------


@app.post(
    "/eventos/suscripciones",
    response_model=Suscripcion,
    status_code=status.HTTP_201_CREATED,
    tags=["observer"],
)
def suscribir(peticion: SolicitudSuscripcion) -> Suscripcion:
    """Registra a un servicio como observador de un tipo de evento."""
    return publicador.suscribir(peticion)


@app.get("/eventos/suscripciones", response_model=list[Suscripcion], tags=["observer"])
def listar_suscripciones() -> list[Suscripcion]:
    return publicador.suscripciones()


@app.delete("/eventos/suscripciones/{suscripcion_id}", tags=["observer"])
def cancelar_suscripcion(suscripcion_id: str) -> dict:
    if not publicador.cancelar(suscripcion_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suscripción no encontrada")
    return {"ok": True}


@app.get("/eventos/estado", tags=["observer"])
def estado_eventos() -> dict:
    return publicador.estado()


@app.get("/eventos/historial", tags=["observer"])
def historial_eventos(limite: Annotated[int, Query(ge=1, le=200)] = 50) -> list[dict]:
    return publicador.historial(limite)


@app.get("/eventos/entregas", tags=["observer"])
def entregas_eventos(limite: Annotated[int, Query(ge=1, le=200)] = 50) -> list[dict]:
    """Traza de cada intento de entrega: evidencia de la comunicación asíncrona."""
    return publicador.entregas(limite)


@app.post("/eventos/reintentar", tags=["observer"])
def reintentar_eventos() -> dict:
    """Reencola los eventos archivados tras recuperar un observador caído."""
    return {"reencolados": publicador.reintentar_fallidos()}
