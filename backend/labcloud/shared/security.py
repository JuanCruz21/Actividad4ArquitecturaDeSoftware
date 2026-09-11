"""Emisión y validación de tokens de acceso.

El Servicio de Usuarios emite los tokens; el API Gateway los valida antes de
direccionar una petición hacia los servicios internos. Concentrar la validación
en el punto de entrada es una de las ventajas del patrón Proxy descrita en el
diseño (sección 8.6.1).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from labcloud.shared.config import JWT_ALGORITHM, JWT_EXPIRA_MINUTOS, JWT_SECRET


class TokenInvalido(Exception):
    """El token no es válido, expiró o fue manipulado."""


def crear_token(*, sujeto: str, usuario_id: str, rol: str) -> tuple[str, datetime]:
    expira = datetime.now(UTC) + timedelta(minutes=JWT_EXPIRA_MINUTOS)
    payload = {
        "sub": sujeto,
        "uid": usuario_id,
        "rol": rol,
        "iss": "labcloud-usuarios",
        "iat": int(datetime.now(UTC).timestamp()),
        "exp": int(expira.timestamp()),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM), expira


def validar_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise TokenInvalido("El token expiró") from exc
    except jwt.PyJWTError as exc:
        raise TokenInvalido("Token inválido") from exc


def token_de_encabezado(authorization: str | None) -> str | None:
    if not authorization:
        return None
    partes = authorization.split()
    if len(partes) == 2 and partes[0].lower() == "bearer":
        return partes[1]
    return None
