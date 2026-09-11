"""Modelo de datos del Servicio de Solicitudes (base propia: data/solicitudes.db)."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from labcloud.shared.db import Base
from labcloud.shared.schemas import nuevo_id

ESTADOS = (
    "registrada",
    "en_cola",
    "en_proceso",
    "resultado_disponible",
    "fallida",
)


class Solicitud(Base):
    __tablename__ = "solicitudes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=nuevo_id)
    codigo: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    cliente_id: Mapped[str] = mapped_column(String(32), index=True)
    cliente_nombre: Mapped[str] = mapped_column(String(160), default="")
    cliente_email: Mapped[str] = mapped_column(String(160), default="")
    muestra_id: Mapped[str] = mapped_column(String(32), default="")
    codigo_muestra: Mapped[str] = mapped_column(String(40), default="")
    tipo_analisis: Mapped[str] = mapped_column(String(60), default="hemograma")
    prioridad: Mapped[str] = mapped_column(String(20), default="normal")
    estado: Mapped[str] = mapped_column(String(30), default="registrada", index=True)
    observaciones: Mapped[str] = mapped_column(Text, default="")
    resultado_id: Mapped[str] = mapped_column(String(32), default="")

    # Trazabilidad del procesamiento concurrente
    hilo_procesamiento: Mapped[str] = mapped_column(String(60), default="")
    espera_cola_ms: Mapped[float] = mapped_column(Float, default=0.0)
    duracion_ms: Mapped[float] = mapped_column(Float, default=0.0)
    intentos: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(String(255), default="")

    creada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    actualizada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )


class EjecucionPrueba(Base):
    """Resultado de una prueba de carga (RF10).

    Guarda la configuración usada y las métricas obtenidas para poder comparar
    escenarios de 1, 2, 4 y 8 hilos.
    """

    __tablename__ = "pruebas_carga"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=nuevo_id)
    etiqueta: Mapped[str] = mapped_column(String(80), default="")
    solicitudes: Mapped[int] = mapped_column(Integer)
    hilos: Mapped[int] = mapped_column(Integer)
    duracion_analisis_s: Mapped[float] = mapped_column(Float, default=0.0)
    tiempo_total_s: Mapped[float] = mapped_column(Float, default=0.0)
    throughput_rps: Mapped[float] = mapped_column(Float, default=0.0)
    latencia_promedio_ms: Mapped[float] = mapped_column(Float, default=0.0)
    latencia_p95_ms: Mapped[float] = mapped_column(Float, default=0.0)
    latencia_maxima_ms: Mapped[float] = mapped_column(Float, default=0.0)
    espera_promedio_ms: Mapped[float] = mapped_column(Float, default=0.0)
    exitosas: Mapped[int] = mapped_column(Integer, default=0)
    fallidas: Mapped[int] = mapped_column(Integer, default=0)
    pico_concurrencia: Mapped[int] = mapped_column(Integer, default=0)
    hilos_utilizados: Mapped[list] = mapped_column(JSON, default=list)
    detalle: Mapped[dict] = mapped_column(JSON, default=dict)
    ejecutada_en: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
