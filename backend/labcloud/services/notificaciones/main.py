"""Servicio de Notificaciones (Nodo 3 - Servicios de soporte, puerto 8003).

Rol en la arquitectura: **observador** del patrón Observer distribuido. Se
suscribe al Servicio de Resultados y recibe el evento ``resultado.disponible``
por HTTP, sin que el productor conozca su lógica interna.

Incluye un interruptor de disponibilidad (``PUT /simulacion/disponibilidad``)
que permite simular una caída temporal y comprobar que el flujo principal de
registro de resultados continúa funcionando (RNF07, sección 8.4.3).
"""

from __future__ import annotations

import logging
import threading
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from labcloud.services.notificaciones.models import Notificacion
from labcloud.services.notificaciones.schemas import EstadoDisponibilidad, NotificacionSalida
from labcloud.shared.config import servicio, url_de
from labcloud.shared.db import Database
from labcloud.shared.events import registrar_observador
from labcloud.shared.schemas import Evento, RespuestaSimple
from labcloud.shared.service import crear_app

log = logging.getLogger("labcloud.notificaciones")
db = Database("notificaciones")

#: Interruptor de simulación de fallo. Cuando está en ``False`` el servicio
#: responde 503 y los eventos quedan archivados en el publicador.
_disponible = threading.Event()
_disponible.set()

TIPO_EVENTO = "resultado.disponible"


def _suscribirse() -> None:
    """Se registra como observador en el Servicio de Resultados.

    Corre en un hilo aparte para no bloquear el arranque: el publicador puede
    tardar en estar disponible.
    """
    spec = servicio("notificaciones")
    registrar_observador(
        publicador_url=url_de("resultados"),
        servicio="notificaciones",
        tipo_evento=TIPO_EVENTO,
        callback_url=f"{spec.base_url}/eventos",
    )


def _inicializar() -> None:
    db.crear_tablas()
    threading.Thread(target=_suscribirse, name="suscripcion-observer", daemon=True).start()


app: FastAPI = crear_app("notificaciones", al_iniciar=_inicializar)
Sesion = Annotated[Session, Depends(db.dependencia)]


def _redactar(evento: Evento) -> tuple[str, str, str]:
    """Construye el mensaje de la notificación a partir de los datos del evento."""
    datos = evento.datos
    destinatario = datos.get("cliente_email") or datos.get("destinatario") or "cliente@labcloud.co"
    if evento.tipo == TIPO_EVENTO:
        asunto = f"Resultado disponible - solicitud {datos.get('codigo_solicitud', 's/n')}"
        mensaje = (
            f"Estimado(a) {datos.get('cliente_nombre', 'cliente')}, el resultado del análisis "
            f"'{datos.get('tipo_analisis', 'general')}' sobre la muestra "
            f"{datos.get('codigo_muestra', 's/n')} ya se encuentra disponible. "
            f"Diagnóstico preliminar: {datos.get('diagnostico', 'ver informe')}."
        )
    else:
        asunto = f"Evento {evento.tipo}"
        mensaje = f"Se recibió el evento '{evento.tipo}' desde el servicio {evento.origen}."
    return destinatario, asunto, mensaje


@app.post("/eventos", response_model=RespuestaSimple, tags=["observer"])
def recibir_evento(evento: Evento, session: Sesion) -> RespuestaSimple:
    """Callback del Observer: recibe un evento publicado por otro servicio."""
    if not _disponible.is_set():
        log.warning(
            "Evento '%s' rechazado: el servicio está simulando una caída", evento.tipo
        )
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Servicio de Notificaciones no disponible (caída simulada)",
        )

    ya_registrada = session.scalar(
        select(Notificacion).where(Notificacion.evento_id == evento.id)
    )
    if ya_registrada:
        # Idempotencia: el publicador reintenta y puede duplicar la entrega.
        log.info("Evento %s ya procesado; se ignora el reintento", evento.id[:8])
        return RespuestaSimple(mensaje="Evento ya procesado")

    destinatario, asunto, mensaje = _redactar(evento)
    notificacion = Notificacion(
        evento_id=evento.id,
        tipo_evento=evento.tipo,
        origen=evento.origen,
        destinatario=destinatario,
        asunto=asunto,
        mensaje=mensaje,
        intento_entrega=evento.intento,
    )
    session.add(notificacion)
    session.flush()

    # Envío simulado: en un entorno real aquí iría el proveedor de correo o SMS.
    log.info("NOTIFICACIÓN ENVIADA -> %s | %s", destinatario, asunto)
    return RespuestaSimple(mensaje=f"Notificación {notificacion.id} generada")


@app.get("/notificaciones", response_model=list[NotificacionSalida], tags=["notificaciones"])
def listar(
    session: Sesion, limite: Annotated[int, Query(ge=1, le=500)] = 50
) -> list[Notificacion]:
    return list(
        session.scalars(
            select(Notificacion).order_by(Notificacion.recibido_en.desc()).limit(limite)
        )
    )


@app.get("/notificaciones/resumen", tags=["notificaciones"])
def resumen(session: Sesion) -> dict:
    total = session.scalar(select(func.count(Notificacion.id))) or 0
    por_tipo = session.execute(
        select(Notificacion.tipo_evento, func.count(Notificacion.id)).group_by(
            Notificacion.tipo_evento
        )
    ).all()
    return {
        "total": total,
        "disponible": _disponible.is_set(),
        "por_tipo": {tipo: cantidad for tipo, cantidad in por_tipo},
    }


@app.put("/simulacion/disponibilidad", tags=["simulación"])
def cambiar_disponibilidad(estado: EstadoDisponibilidad) -> dict:
    """Simula la caída o recuperación del servicio secundario.

    Con el servicio "caído", el Servicio de Resultados sigue registrando
    resultados con normalidad y los eventos quedan archivados para reintento.
    """
    if estado.disponible:
        _disponible.set()
        log.info("Servicio de Notificaciones restablecido")
    else:
        _disponible.clear()
        log.warning("Caída simulada activada: los eventos serán rechazados")
    return {"disponible": _disponible.is_set()}
