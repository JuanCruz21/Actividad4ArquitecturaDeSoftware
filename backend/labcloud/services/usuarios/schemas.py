"""Esquemas de entrada y salida del Servicio de Usuarios."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

ROLES = ("administrador", "recepcionista", "analista", "cliente")


class UsuarioCrear(BaseModel):
    nombre: str = Field(min_length=2, max_length=120)
    email: EmailStr
    clave: str = Field(min_length=4, max_length=128)
    rol: str = Field(default="recepcionista", pattern="|".join(ROLES))


class UsuarioSalida(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    nombre: str
    email: EmailStr
    rol: str
    activo: bool
    creado_en: datetime


class Credenciales(BaseModel):
    email: EmailStr
    clave: str


class TokenSalida(BaseModel):
    token: str
    tipo: str = "bearer"
    expira_en: datetime
    usuario: UsuarioSalida
