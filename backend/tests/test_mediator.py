"""Pruebas del patrón Mediator.

La propiedad que se verifica es la del patrón: los servicios participantes no
se llaman entre sí; toda la coordinación pasa por el mediador, y este ejecuta
los pasos en el orden definido por el diseño.
"""

from __future__ import annotations

import threading
from typing import Any

import pytest

from labcloud.services.solicitudes.mediator import ErrorMediacion, MediadorAnalisis
from labcloud.shared.http_client import ServicioNoDisponible


class ColegaFalso:
    """Sustituye a un ClienteServicio y registra las llamadas recibidas."""

    def __init__(self, respuestas: dict[str, Any] | None = None, caido: bool = False) -> None:
        self.respuestas = respuestas or {}
        self.caido = caido
        self.llamadas: list[tuple[str, str]] = []

    def json(self, metodo: str, ruta: str, **_kwargs: Any) -> Any:
        self.llamadas.append((metodo, ruta))
        if self.caido:
            raise ServicioNoDisponible("falso", "simulación de caída")
        return self.respuestas.get(ruta, {"id": "generado"})

    def patch(self, ruta: str, **_kwargs: Any) -> Any:
        self.llamadas.append(("PATCH", ruta))
        if self.caido:
            raise ServicioNoDisponible("falso", "simulación de caída")
        return None

    def cerrar(self) -> None:
        pass


@pytest.fixture
def mediador():
    m = MediadorAnalisis()
    m._colegas = {
        "clientes": ColegaFalso(
            {"/clientes/c1": {"id": "c1", "nombre": "Laura", "email": "l@x.co"}}
        ),
        "muestras": ColegaFalso({"/muestras/m1": {"id": "m1", "codigo": "MU-1"}}),
        "resultados": ColegaFalso({"/resultados": {"id": "r1", "diagnostico": "normal"}}),
    }
    m._llamadas = {k: 0 for k in m._colegas}
    return m


CONTEXTO = {
    "solicitud_id": "s1",
    "codigo": "SOL-1",
    "cliente_id": "c1",
    "cliente_nombre": "Laura",
    "cliente_email": "l@x.co",
    "muestra_id": "m1",
    "codigo_muestra": "MU-1",
    "tipo_analisis": "hemograma",
    "observaciones": "",
}


def test_el_mediador_coordina_los_pasos_en_orden(mediador) -> None:
    resultado = mediador.procesar(CONTEXTO, duracion_analisis_s=0.0)

    assert resultado["id"] == "r1"
    assert mediador._colegas["muestras"].llamadas == [
        ("PATCH", "/muestras/m1/estado"),
        ("PATCH", "/muestras/m1/estado"),
    ], "La muestra debe marcarse al iniciar y al terminar el análisis"
    assert mediador._colegas["resultados"].llamadas == [("POST", "/resultados")]


def test_el_resultado_registra_el_hilo_que_lo_produjo(mediador) -> None:
    capturado: dict[str, Any] = {}

    def registrar(metodo: str, ruta: str, **kwargs: Any) -> Any:
        capturado.update(kwargs.get("json", {}))
        return {"id": "r1"}

    mediador._colegas["resultados"].json = registrar  # type: ignore[method-assign]
    mediador.procesar(CONTEXTO, duracion_analisis_s=0.0)

    assert capturado["hilo_origen"] == threading.current_thread().name
    assert capturado["codigo_solicitud"] == "SOL-1"
    assert capturado["valores"], "El resultado debe traer los valores del análisis"


def test_si_resultados_no_responde_la_mediacion_falla(mediador) -> None:
    mediador._colegas["resultados"].caido = True
    with pytest.raises(ErrorMediacion, match="registrar el resultado"):
        mediador.procesar(CONTEXTO, duracion_analisis_s=0.0)


def test_una_falla_en_muestras_no_detiene_el_analisis(mediador) -> None:
    """Marcar la muestra es secundario: su caída no debe frenar el resultado."""
    mediador._colegas["muestras"].caido = True
    resultado = mediador.procesar(CONTEXTO, duracion_analisis_s=0.0)
    assert resultado["id"] == "r1"


def test_se_valida_el_cliente_antes_de_aceptar_la_solicitud(mediador) -> None:
    cliente = mediador.obtener_cliente("c1")
    assert cliente["nombre"] == "Laura"

    mediador._colegas["clientes"].caido = True
    with pytest.raises(ErrorMediacion, match="validar el cliente"):
        mediador.obtener_cliente("c1")


def test_el_mediador_contabiliza_las_llamadas_por_colega(mediador) -> None:
    mediador.procesar(CONTEXTO, duracion_analisis_s=0.0)
    estado = mediador.estado()
    assert estado["llamadas_por_colega"]["resultados"] == 1
    assert estado["llamadas_por_colega"]["muestras"] == 2
    assert estado["total_llamadas"] == 3
