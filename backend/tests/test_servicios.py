"""Pruebas de cada servicio de forma aislada.

Se ejercita el contrato HTTP de los servicios que no dependen de otros, y se
comprueba que cada uno expone su identidad de nodo en ``/health``.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from labcloud.services.clientes.main import app as app_clientes
from labcloud.services.muestras.main import app as app_muestras
from labcloud.services.notificaciones.main import app as app_notificaciones
from labcloud.services.resultados.main import app as app_resultados
from labcloud.services.usuarios.main import app as app_usuarios


@pytest.fixture
def usuarios():
    with TestClient(app_usuarios) as c:
        yield c


@pytest.fixture
def clientes():
    with TestClient(app_clientes) as c:
        yield c


@pytest.fixture
def muestras():
    with TestClient(app_muestras) as c:
        yield c


@pytest.fixture
def resultados():
    with TestClient(app_resultados) as c:
        yield c


@pytest.fixture
def notificaciones():
    with TestClient(app_notificaciones) as c:
        yield c


# --- Identidad de nodo ------------------------------------------------------


def test_cada_servicio_declara_su_nodo(usuarios, clientes, muestras, resultados) -> None:
    esperado = {
        (usuarios, "usuarios", "nodo-1", 8004),
        (clientes, "clientes", "nodo-4", 8005),
        (muestras, "muestras", "nodo-4", 8006),
        (resultados, "resultados", "nodo-3", 8002),
    }
    for cliente, service_id, nodo, puerto in esperado:
        salud = cliente.get("/health").json()
        assert salud["servicio"] == service_id
        assert salud["nodo"] == nodo
        assert salud["puerto"] == puerto
        assert salud["hilos_activos"] >= 1


# --- Servicio de Usuarios ---------------------------------------------------


def test_login_con_credenciales_validas_emite_un_token(usuarios) -> None:
    respuesta = usuarios.post(
        "/auth/login", json={"email": "admin@labcloud.co", "clave": "admin123"}
    )
    assert respuesta.status_code == 200
    datos = respuesta.json()
    assert datos["usuario"]["rol"] == "administrador"
    assert usuarios.post("/auth/verificar", json={"token": datos["token"]}).json()["valido"]


def test_login_con_clave_incorrecta_se_rechaza(usuarios) -> None:
    respuesta = usuarios.post(
        "/auth/login", json={"email": "admin@labcloud.co", "clave": "incorrecta"}
    )
    assert respuesta.status_code == 401


def test_no_se_permiten_correos_duplicados(usuarios) -> None:
    nuevo = {
        "nombre": "Prueba Duplicado",
        "email": "duplicado@labcloud.co",
        "clave": "clave123",
        "rol": "analista",
    }
    assert usuarios.post("/usuarios", json=nuevo).status_code == 201
    assert usuarios.post("/usuarios", json=nuevo).status_code == 409


# --- Servicio de Clientes y Muestras ----------------------------------------


def test_registrar_y_consultar_un_cliente(clientes) -> None:
    creado = clientes.post(
        "/clientes",
        json={
            "documento": "CC-PRUEBA-1",
            "nombre": "Cliente de prueba",
            "email": "prueba@labcloud.co",
        },
    )
    assert creado.status_code == 201
    identificador = creado.json()["id"]
    assert clientes.get(f"/clientes/{identificador}").json()["nombre"] == "Cliente de prueba"
    assert clientes.get("/clientes/inexistente").status_code == 404


def test_el_estado_de_la_muestra_avanza(muestras) -> None:
    creada = muestras.post(
        "/muestras", json={"codigo": "MU-PRUEBA-1", "cliente_id": "c1", "tipo": "sangre"}
    ).json()
    assert creada["estado"] == "recibida"

    actualizada = muestras.patch(
        f"/muestras/{creada['id']}/estado", json={"estado": "procesada"}
    )
    assert actualizada.json()["estado"] == "procesada"


def test_no_se_aceptan_estados_invalidos(muestras) -> None:
    creada = muestras.post(
        "/muestras", json={"codigo": "MU-PRUEBA-2", "cliente_id": "c1", "tipo": "orina"}
    ).json()
    respuesta = muestras.patch(
        f"/muestras/{creada['id']}/estado", json={"estado": "inventado"}
    )
    assert respuesta.status_code == 422


# --- Servicio de Resultados (sujeto observable) -----------------------------


def test_registrar_un_resultado_publica_un_evento(resultados) -> None:
    antes = resultados.get("/eventos/estado").json()["eventos_publicados"]
    creado = resultados.post(
        "/resultados",
        json={
            "solicitud_id": "s-prueba",
            "codigo_solicitud": "SOL-PRUEBA",
            "tipo_analisis": "glucosa",
            "diagnostico": "Dentro de parámetros normales",
            "hilo_origen": "solicitud-worker_0",
        },
    )
    assert creado.status_code == 201
    despues = resultados.get("/eventos/estado").json()
    assert despues["eventos_publicados"] == antes + 1
    assert despues["activo"] is True


def test_se_pueden_registrar_y_cancelar_observadores(resultados) -> None:
    suscripcion = resultados.post(
        "/eventos/suscripciones",
        json={
            "servicio": "auditoria",
            "tipo_evento": "resultado.disponible",
            "callback_url": "http://127.0.0.1:9999/eventos",
        },
    ).json()
    assert any(
        s["servicio"] == "auditoria" for s in resultados.get("/eventos/suscripciones").json()
    )
    assert resultados.delete(f"/eventos/suscripciones/{suscripcion['id']}").status_code == 200
    assert resultados.delete("/eventos/suscripciones/inexistente").status_code == 404


# --- Servicio de Notificaciones (observador) --------------------------------


def test_el_observador_genera_una_notificacion(notificaciones) -> None:
    evento = {
        "id": "evento-prueba-1",
        "tipo": "resultado.disponible",
        "origen": "resultados",
        "ocurrido_en": "2026-09-11T10:00:00Z",
        "datos": {
            "codigo_solicitud": "SOL-99",
            "cliente_nombre": "Laura",
            "cliente_email": "laura@correo.co",
            "codigo_muestra": "MU-99",
            "tipo_analisis": "hemograma",
            "diagnostico": "Dentro de parámetros normales",
        },
    }
    assert notificaciones.post("/eventos", json=evento).status_code == 200
    generadas = notificaciones.get("/notificaciones").json()
    assert generadas[0]["destinatario"] == "laura@correo.co"
    assert "SOL-99" in generadas[0]["asunto"]


def test_el_mismo_evento_no_se_procesa_dos_veces(notificaciones) -> None:
    """Idempotencia: el publicador puede reintentar una entrega ya realizada."""
    evento = {
        "id": "evento-prueba-2",
        "tipo": "resultado.disponible",
        "origen": "resultados",
        "ocurrido_en": "2026-09-11T10:00:00Z",
        "datos": {"codigo_solicitud": "SOL-100", "cliente_email": "a@b.co"},
    }
    notificaciones.post("/eventos", json=evento)
    total = notificaciones.get("/notificaciones/resumen").json()["total"]
    notificaciones.post("/eventos", json=evento)
    assert notificaciones.get("/notificaciones/resumen").json()["total"] == total


def test_la_caida_simulada_rechaza_los_eventos(notificaciones) -> None:
    notificaciones.put("/simulacion/disponibilidad", json={"disponible": False})
    respuesta = notificaciones.post(
        "/eventos",
        json={
            "id": "evento-prueba-3",
            "tipo": "resultado.disponible",
            "origen": "resultados",
            "ocurrido_en": "2026-09-11T10:00:00Z",
            "datos": {},
        },
    )
    assert respuesta.status_code == 503
    notificaciones.put("/simulacion/disponibilidad", json={"disponible": True})
    assert notificaciones.get("/notificaciones/resumen").json()["disponible"] is True
