"""Modelo de datos del Servicio de Clientes (base propia: data/clientes.db)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from labcloud.shared.db import Base
from labcloud.shared.schemas import nuevo_id


class Cliente(Base):
    __tablename__ = "clientes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=nuevo_id)
    documento: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    nombre: Mapped[str] = mapped_column(String(160))
    email: Mapped[str] = mapped_column(String(160))
    telefono: Mapped[str] = mapped_column(String(40), default="")
    ciudad: Mapped[str] = mapped_column(String(80), default="")
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
    creado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
