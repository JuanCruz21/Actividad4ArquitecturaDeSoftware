"""Servicio de Usuarios (Nodo 1 - Entrada y acceso, puerto 8004).

Responsabilidad: registro de usuarios, autenticación, roles y permisos.
Emite los tokens que el API Gateway valida antes de direccionar cada petición.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from labcloud.services.usuarios.models import Usuario
from labcloud.services.usuarios.schemas import (
    Credenciales,
    TokenSalida,
    UsuarioCrear,
    UsuarioSalida,
)
from labcloud.shared.db import Database
from labcloud.shared.security import TokenInvalido, crear_token, validar_token
from labcloud.shared.service import crear_app

log = logging.getLogger("labcloud.usuarios")
db = Database("usuarios")

ITERACIONES = 120_000

USUARIOS_DEMO = [
    ("Administrador LabCloud", "admin@labcloud.co", "admin123", "administrador"),
    ("Maria Carolina Tafur", "recepcion@labcloud.co", "labcloud", "recepcionista"),
    ("David Jiménez Sánchez", "analista@labcloud.co", "labcloud", "analista"),
]


def _hash_clave(clave: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    derivada = hashlib.pbkdf2_hmac("sha256", clave.encode(), salt, ITERACIONES)
    return f"pbkdf2_sha256${ITERACIONES}${salt.hex()}${derivada.hex()}"


def _verificar_clave(clave: str, guardado: str) -> bool:
    try:
        _, iteraciones, salt_hex, esperado = guardado.split("$")
        derivada = hashlib.pbkdf2_hmac(
            "sha256", clave.encode(), bytes.fromhex(salt_hex), int(iteraciones)
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(derivada.hex(), esperado)


def _sembrar() -> None:
    """Crea las cuentas de demostración la primera vez que arranca el servicio."""
    with db.sesion() as session:
        if session.scalar(select(Usuario).limit(1)):
            return
        for nombre, email, clave, rol in USUARIOS_DEMO:
            session.add(
                Usuario(nombre=nombre, email=email, clave_hash=_hash_clave(clave), rol=rol)
            )
        log.info("Usuarios de demostración creados (%d)", len(USUARIOS_DEMO))


def _inicializar() -> None:
    db.crear_tablas()
    _sembrar()


app: FastAPI = crear_app("usuarios", al_iniciar=_inicializar)
Sesion = Annotated[Session, Depends(db.dependencia)]


@app.post(
    "/usuarios",
    response_model=UsuarioSalida,
    status_code=status.HTTP_201_CREATED,
    tags=["usuarios"],
)
def crear_usuario(datos: UsuarioCrear, session: Sesion) -> Usuario:
    if session.scalar(select(Usuario).where(Usuario.email == datos.email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "El correo ya se encuentra registrado")
    usuario = Usuario(
        nombre=datos.nombre,
        email=str(datos.email),
        clave_hash=_hash_clave(datos.clave),
        rol=datos.rol,
    )
    session.add(usuario)
    session.flush()
    log.info("Usuario registrado: %s (%s)", usuario.email, usuario.rol)
    return usuario


@app.get("/usuarios", response_model=list[UsuarioSalida], tags=["usuarios"])
def listar_usuarios(
    session: Sesion, limite: Annotated[int, Query(ge=1, le=200)] = 100
) -> list[Usuario]:
    return list(session.scalars(select(Usuario).order_by(Usuario.creado_en.desc()).limit(limite)))


@app.get("/usuarios/{usuario_id}", response_model=UsuarioSalida, tags=["usuarios"])
def obtener_usuario(usuario_id: str, session: Sesion) -> Usuario:
    usuario = session.get(Usuario, usuario_id)
    if not usuario:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    return usuario


@app.post("/auth/login", response_model=TokenSalida, tags=["autenticación"])
def login(credenciales: Credenciales, session: Sesion) -> TokenSalida:
    usuario = session.scalar(select(Usuario).where(Usuario.email == str(credenciales.email)))
    if not usuario or not _verificar_clave(credenciales.clave, usuario.clave_hash):
        log.warning("Intento de acceso fallido para %s", credenciales.email)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas")
    if not usuario.activo:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "El usuario se encuentra inactivo")

    token, expira = crear_token(sujeto=usuario.email, usuario_id=usuario.id, rol=usuario.rol)
    log.info("Acceso concedido a %s (%s)", usuario.email, usuario.rol)
    return TokenSalida(
        token=token, expira_en=expira, usuario=UsuarioSalida.model_validate(usuario)
    )


@app.post("/auth/verificar", tags=["autenticación"])
def verificar(payload: dict) -> dict:
    """Valida un token. La usa el API Gateway al aplicar el patrón Proxy."""
    token = payload.get("token", "")
    try:
        datos = validar_token(token)
    except TokenInvalido as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc
    return {"valido": True, "usuario_id": datos["uid"], "email": datos["sub"], "rol": datos["rol"]}
