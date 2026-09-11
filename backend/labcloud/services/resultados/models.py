"""Modelo de datos del Servicio de Resultados (base propia: data/resultados.db)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from labcloud.shared.db import Base
from labcloud.shared.schemas import nuevo_id


class Resultado(Base):
    __tablename__ = "resultados"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=nuevo_id)
    solicitud_id: Mapped[str] = mapped_column(String(32), index=True)
    codigo_solicitud: Mapped[str] = mapped_column(String(40), default="")
    cliente_id: Mapped[str] = mapped_column(String(32), default="")
    cliente_nombre: Mapped[str] = mapped_column(String(160), default="")
    cliente_email: Mapped[str] = mapped_column(String(160), default="")
    muestra_id: Mapped[str] = mapped_column(String(32), default="")
    codigo_muestra: Mapped[str] = mapped_column(String(40), default="")
    tipo_analisis: Mapped[str] = mapped_column(String(60), default="general")
    valores: Mapped[dict] = mapped_column(JSON, default=dict)
    diagnostico: Mapped[str] = mapped_column(String(200), default="")
    observaciones: Mapped[str] = mapped_column(Text, default="")
    # Trazabilidad de la concurrencia: hilo del pool que produjo el resultado.
    hilo_origen: Mapped[str] = mapped_column(String(60), default="")
    duracion_ms: Mapped[float] = mapped_column(Float, default=0.0)
    registrado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class EventoPublicado(Base):
    """Bitácora persistente de los eventos emitidos por este servicio."""

    __tablename__ = "eventos_publicados"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    tipo: Mapped[str] = mapped_column(String(60), index=True)
    origen: Mapped[str] = mapped_column(String(40))
    datos: Mapped[dict] = mapped_column(JSON, default=dict)
    publicado_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
