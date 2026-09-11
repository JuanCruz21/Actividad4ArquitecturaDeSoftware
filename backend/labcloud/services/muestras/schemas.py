"""Esquemas del Servicio de Muestras."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TipoMuestra = Literal["sangre", "orina", "tejido", "saliva", "hisopado", "otro"]
EstadoMuestra = Literal["recibida", "en_analisis", "procesada", "descartada"]


class MuestraCrear(BaseModel):
    codigo: str = Field(min_length=3, max_length=40)
    cliente_id: str = Field(min_length=1, max_length=32)
    tipo: TipoMuestra = "sangre"
    descripcion: str = Field(default="", max_length=255)


class MuestraEstado(BaseModel):
    estado: EstadoMuestra


class MuestraSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    codigo: str
    cliente_id: str
    tipo: str
    descripcion: str
    estado: str
    recibida_en: datetime
