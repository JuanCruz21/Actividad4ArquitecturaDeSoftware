"""Esquemas del Servicio de Notificaciones."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificacionSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    evento_id: str
    tipo_evento: str
    origen: str
    destinatario: str
    canal: str
    asunto: str
    mensaje: str
    estado: str
    intento_entrega: int
    recibido_en: datetime


class EstadoDisponibilidad(BaseModel):
    """Interruptor para simular la caída temporal del servicio (sección 8.4.3)."""

    disponible: bool
