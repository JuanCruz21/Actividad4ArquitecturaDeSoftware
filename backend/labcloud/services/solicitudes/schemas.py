"""Esquemas del Servicio de Solicitudes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

TipoAnalisis = Literal[
    "hemograma", "perfil_lipidico", "glucosa", "uroanalisis", "cultivo", "covid19", "general"
]
Prioridad = Literal["baja", "normal", "alta", "urgente"]


class SolicitudCrear(BaseModel):
    cliente_id: str = Field(min_length=1, max_length=32)
    muestra_id: str = Field(default="", max_length=32)
    tipo_analisis: TipoAnalisis = "hemograma"
    prioridad: Prioridad = "normal"
    observaciones: str = Field(default="", max_length=500)
    #: ``False`` devuelve 202 y el análisis continúa en un hilo del pool.
    esperar_resultado: bool = True


class SolicitudSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    codigo: str
    cliente_id: str
    cliente_nombre: str
    cliente_email: str
    muestra_id: str
    codigo_muestra: str
    tipo_analisis: str
    prioridad: str
    estado: str
    observaciones: str
    resultado_id: str
    hilo_procesamiento: str
    espera_cola_ms: float
    duracion_ms: float
    intentos: int
    error: str
    creada_en: datetime
    actualizada_en: datetime


class ConfiguracionHilos(BaseModel):
    """Ajuste en caliente del pool de procesamiento."""

    hilos: int = Field(ge=1, le=64)


class PruebaCargaPeticion(BaseModel):
    """Parámetros de una prueba de concurrencia (RF09)."""

    solicitudes: int = Field(default=20, ge=1, le=500)
    hilos: int | None = Field(default=None, ge=1, le=64)
    etiqueta: str = Field(default="", max_length=80)
    duracion_analisis_s: float | None = Field(default=None, ge=0.0, le=5.0)
    cliente_id: str = ""
    tipo_analisis: TipoAnalisis = "hemograma"
    #: Si es ``True`` no se llama a los demás servicios: aísla el costo del pool.
    aislar_pool: bool = False


class ComparativaPeticion(BaseModel):
    """Ejecuta la misma carga con varias configuraciones de hilos."""

    solicitudes: int = Field(default=20, ge=1, le=300)
    configuraciones: list[int] = Field(default=[1, 2, 4, 8], min_length=1, max_length=8)
    duracion_analisis_s: float | None = Field(default=None, ge=0.0, le=5.0)
    aislar_pool: bool = True


class PruebaCargaSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    etiqueta: str
    solicitudes: int
    hilos: int
    duracion_analisis_s: float
    tiempo_total_s: float
    throughput_rps: float
    latencia_promedio_ms: float
    latencia_p95_ms: float
    latencia_maxima_ms: float
    espera_promedio_ms: float
    exitosas: int
    fallidas: int
    pico_concurrencia: int
    hilos_utilizados: list[str]
    detalle: dict[str, Any]
    ejecutada_en: datetime
