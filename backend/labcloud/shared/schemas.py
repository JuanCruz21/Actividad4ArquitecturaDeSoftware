"""Esquemas compartidos entre los servicios distribuidos."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


def ahora() -> datetime:
    return datetime.now(UTC)


def nuevo_id() -> str:
    return uuid.uuid4().hex


class SaludServicio(BaseModel):
    """Respuesta de ``GET /health``: identifica al proceso y su nodo lógico."""

    servicio: str
    nombre: str
    nodo: str
    nodo_nombre: str
    puerto: int
    pid: int
    estado: Literal["activo", "degradado"] = "activo"
    hilos_activos: int
    version: str
    uptime_segundos: float
    patrones: list[str] = Field(default_factory=list)


class Evento(BaseModel):
    """Sobre de evento del Observer distribuido.

    Un evento viaja del servicio que lo produce (sujeto) hacia los servicios
    suscritos (observadores) mediante HTTP, sin que el productor conozca la
    lógica interna del consumidor.
    """

    id: str = Field(default_factory=nuevo_id)
    tipo: str
    origen: str
    ocurrido_en: datetime = Field(default_factory=ahora)
    intento: int = 1
    datos: dict[str, Any] = Field(default_factory=dict)


class Suscripcion(BaseModel):
    """Registro de un observador interesado en un tipo de evento."""

    id: str = Field(default_factory=nuevo_id)
    servicio: str
    tipo_evento: str
    callback_url: str
    activa: bool = True
    creada_en: datetime = Field(default_factory=ahora)


class SolicitudSuscripcion(BaseModel):
    servicio: str
    tipo_evento: str
    callback_url: str


class RespuestaSimple(BaseModel):
    ok: bool = True
    mensaje: str = ""
