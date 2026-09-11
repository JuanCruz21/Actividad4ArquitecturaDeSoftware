"""Esquemas del Servicio de Clientes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ClienteCrear(BaseModel):
    documento: str = Field(min_length=4, max_length=40)
    nombre: str = Field(min_length=2, max_length=160)
    email: EmailStr
    telefono: str = Field(default="", max_length=40)
    ciudad: str = Field(default="", max_length=80)


class ClienteSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    documento: str
    nombre: str
    email: EmailStr
    telefono: str
    ciudad: str
    activo: bool
    creado_en: datetime
