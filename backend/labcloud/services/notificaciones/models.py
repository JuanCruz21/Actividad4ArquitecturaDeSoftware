"""Modelo de datos del Servicio de Notificaciones (base propia)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from labcloud.shared.db import Base
from labcloud.shared.schemas import nuevo_id


class Notificacion(Base):
    __tablename__ = "notificaciones"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=nuevo_id)
    evento_id: Mapped[str] = mapped_column(String(32), index=True)
    tipo_evento: Mapped[str] = mapped_column(String(60), index=True)
    origen: Mapped[str] = mapped_column(String(40))
    destinatario: Mapped[str] = mapped_column(String(160))
    canal: Mapped[str] = mapped_column(String(30), default="email")
    asunto: Mapped[str] = mapped_column(String(200))
    mensaje: Mapped[str] = mapped_column(Text)
    estado: Mapped[str] = mapped_column(String(30), default="enviada")
    intento_entrega: Mapped[int] = mapped_column(Integer, default=1)
    recibido_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
