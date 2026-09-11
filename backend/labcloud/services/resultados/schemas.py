"""Esquemas del Servicio de Resultados."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResultadoCrear(BaseModel):
    solicitud_id: str = Field(min_length=1, max_length=32)
    codigo_solicitud: str = ""
    cliente_id: str = ""
    cliente_nombre: str = ""
    cliente_email: str = ""
    muestra_id: str = ""
    codigo_muestra: str = ""
    tipo_analisis: str = "general"
    valores: dict[str, Any] = Field(default_factory=dict)
    diagnostico: str = ""
    observaciones: str = ""
    hilo_origen: str = ""
    duracion_ms: float = 0.0


class ResultadoSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    solicitud_id: str
    codigo_solicitud: str
    cliente_id: str
    cliente_nombre: str
    cliente_email: str
    muestra_id: str
    codigo_muestra: str
    tipo_analisis: str
    valores: dict[str, Any]
    diagnostico: str
    observaciones: str
    hilo_origen: str
    duracion_ms: float
    registrado_en: datetime
