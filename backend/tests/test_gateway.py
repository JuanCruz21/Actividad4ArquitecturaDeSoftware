"""Pruebas del API Gateway (patrón Proxy).

Se centran en la tabla de enrutamiento y la política de acceso, que son las
dos responsabilidades que el Gateway añade antes de reenviar una petición.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from labcloud.gateway.main import app
from labcloud.gateway.routing import resolver
from labcloud.shared.security import TokenInvalido, crear_token, validar_token


@pytest.fixture
def cliente():
    with TestClient(app) as c:
        yield c


@pytest.mark.parametrize(
    ("publica", "servicio", "interna"),
    [
        ("/api/solicitudes", "solicitudes", "/solicitudes"),
        ("/api/solicitudes/abc123", "solicitudes", "/solicitudes/abc123"),
        ("/api/concurrencia", "solicitudes", "/concurrencia"),
        ("/api/eventos/suscripciones", "resultados", "/eventos/suscripciones"),
        ("/api/auth/login", "usuarios", "/auth/login"),
        ("/api/notificaciones/resumen", "notificaciones", "/notificaciones/resumen"),
    ],
)
def test_la_tabla_de_rutas_resuelve_el_servicio(publica, servicio, interna) -> None:
    resultado = resolver(publica)
    assert resultado is not None, f"No se resolvió {publica}"
    ruta, ruta_interna = resultado
    assert ruta.servicio == servicio
    assert ruta_interna == interna


def test_una_ruta_desconocida_no_se_reenvia(cliente) -> None:
    respuesta = cliente.get("/api/inexistente")
    assert respuesta.status_code == 404
    assert "no existe una ruta registrada" in respuesta.json()["detail"].lower()


def test_la_escritura_sin_token_se_rechaza_en_el_gateway(cliente) -> None:
    """El Proxy corta la petición antes de tocar el servicio interno."""
    respuesta = cliente.post("/api/clientes", json={"documento": "X", "nombre": "Y"})
    assert respuesta.status_code == 401


def test_las_rutas_de_autenticacion_son_publicas() -> None:
    ruta, _ = resolver("/api/auth/login")
    assert ruta.publico is True


def test_el_gateway_describe_la_arquitectura(cliente) -> None:
    datos = cliente.get("/arquitectura").json()
    assert {n["id"] for n in datos["nodos"]} == {"nodo-1", "nodo-2", "nodo-3", "nodo-4"}
    assert {p["nombre"] for p in datos["patrones"]} == {
        "Proxy",
        "Mediator",
        "Observer distribuido",
    }
    puertos = {s["puerto"] for n in datos["nodos"] for s in n["servicios"]}
    assert {8000, 8001, 8002, 8003}.issubset(puertos)


def test_el_token_emitido_es_valido_y_transporta_el_rol() -> None:
    token, _ = crear_token(sujeto="ana@labcloud.co", usuario_id="u1", rol="analista")
    datos = validar_token(token)
    assert datos["sub"] == "ana@labcloud.co"
    assert datos["rol"] == "analista"


def test_un_token_manipulado_se_rechaza() -> None:
    token, _ = crear_token(sujeto="ana@labcloud.co", usuario_id="u1", rol="analista")
    with pytest.raises(TokenInvalido):
        validar_token(token[:-4] + "aaaa")
