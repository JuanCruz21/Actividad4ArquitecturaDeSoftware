"""Pruebas del Observer distribuido.

Comprueban que publicar un evento no bloquea al productor, que los
observadores reciben lo que les corresponde y que la caída de un observador no
interrumpe el flujo principal (RNF07).
"""

from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from labcloud.shared.events import PublicadorEventos
from labcloud.shared.schemas import SolicitudSuscripcion


class ObservadorFalso:
    """Servidor HTTP mínimo que hace de observador en las pruebas."""

    def __init__(self) -> None:
        self.recibidos: list[dict] = []
        self.disponible = True
        observador = self

        class Manejador(BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 - nombre exigido por la librería
                longitud = int(self.headers.get("content-length", 0))
                cuerpo = self.rfile.read(longitud)
                if not observador.disponible:
                    self.send_response(503)
                    self.end_headers()
                    return
                import json

                observador.recibidos.append(json.loads(cuerpo))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *_args: object) -> None:
                pass

        self.servidor = HTTPServer(("127.0.0.1", 0), Manejador)
        self.puerto = self.servidor.server_address[1]
        self.hilo = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        self.hilo.start()

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.puerto}/eventos"

    def cerrar(self) -> None:
        self.servidor.shutdown()
        self.servidor.server_close()


@pytest.fixture
def observador():
    o = ObservadorFalso()
    yield o
    o.cerrar()


@pytest.fixture
def publicador():
    p = PublicadorEventos("pruebas", despachadores=2, timeout=1.0)
    p.iniciar()
    yield p
    p.detener()


def _esperar(condicion, limite: float = 6.0) -> bool:
    fin = time.time() + limite
    while time.time() < fin:
        if condicion():
            return True
        time.sleep(0.05)
    return False


def test_el_observador_recibe_el_evento(publicador, observador) -> None:
    publicador.suscribir(
        SolicitudSuscripcion(
            servicio="notificaciones",
            tipo_evento="resultado.disponible",
            callback_url=observador.url,
        )
    )
    publicador.publicar("resultado.disponible", {"codigo_solicitud": "SOL-1"})

    assert _esperar(lambda: len(observador.recibidos) == 1), "El evento nunca llegó"
    assert observador.recibidos[0]["datos"]["codigo_solicitud"] == "SOL-1"
    assert observador.recibidos[0]["origen"] == "pruebas"


def test_publicar_no_bloquea_al_productor(publicador, observador) -> None:
    """El productor no debe esperar a la entrega: solo encola."""
    observador.disponible = False
    publicador.suscribir(
        SolicitudSuscripcion(
            servicio="notificaciones",
            tipo_evento="resultado.disponible",
            callback_url=observador.url,
        )
    )

    inicio = time.perf_counter()
    publicador.publicar("resultado.disponible", {"codigo_solicitud": "SOL-2"})
    transcurrido = time.perf_counter() - inicio

    assert transcurrido < 0.1, f"publicar() bloqueó {transcurrido:.3f} s"


def test_un_observador_caido_no_pierde_el_evento(publicador, observador) -> None:
    """Los eventos no entregados se archivan y pueden reintentarse (RNF07)."""
    observador.disponible = False
    publicador.suscribir(
        SolicitudSuscripcion(
            servicio="notificaciones",
            tipo_evento="resultado.disponible",
            callback_url=observador.url,
        )
    )
    publicador.publicar("resultado.disponible", {"codigo_solicitud": "SOL-3"})

    assert _esperar(lambda: publicador.estado()["eventos_archivados"] == 1, limite=15)
    assert observador.recibidos == []

    observador.disponible = True
    assert publicador.reintentar_fallidos() == 1
    assert _esperar(lambda: len(observador.recibidos) == 1)
    assert observador.recibidos[0]["datos"]["codigo_solicitud"] == "SOL-3"


def test_solo_se_notifica_a_los_suscritos_al_tipo(publicador, observador) -> None:
    publicador.suscribir(
        SolicitudSuscripcion(
            servicio="notificaciones",
            tipo_evento="resultado.disponible",
            callback_url=observador.url,
        )
    )
    publicador.publicar("solicitud.creada", {"codigo_solicitud": "SOL-4"})
    time.sleep(0.4)
    assert observador.recibidos == []


def test_cancelar_la_suscripcion_detiene_las_entregas(publicador, observador) -> None:
    suscripcion = publicador.suscribir(
        SolicitudSuscripcion(
            servicio="notificaciones",
            tipo_evento="resultado.disponible",
            callback_url=observador.url,
        )
    )
    assert publicador.cancelar(suscripcion.id) is True

    publicador.publicar("resultado.disponible", {"codigo_solicitud": "SOL-5"})
    time.sleep(0.4)
    assert observador.recibidos == []
