"""Modelo de datos del Servicio de Muestras (base propia: data/muestras.db)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from labcloud.shared.db import Base
from labcloud.shared.schemas import nuevo_id


class Muestra(Base):
    __tablename__ = "muestras"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=nuevo_id)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    # Referencia por identificador al Servicio de Clientes: no hay llave foránea
    # entre bases porque cada servicio posee su propio almacenamiento.
    cliente_id: Mapped[str] = mapped_column(String(32), index=True)
    tipo: Mapped[str] = mapped_column(String(60))
    descripcion: Mapped[str] = mapped_column(String(255), default="")
    estado: Mapped[str] = mapped_column(String(30), default="recibida")
    recibida_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
