"""Pruebas del pool de hilos del Servicio de Solicitudes.

Verifican el comportamiento que el diseño exige en la sección 8.5: varias
solicitudes se procesan de forma concurrente, las que exceden la cantidad de
hilos esperan en cola, y la configuración puede cambiarse en caliente.
"""

from __future__ import annotations

import threading
import time

from labcloud.services.solicitudes.pool import PoolProcesamiento


def _tarea(duracion: float = 0.15) -> str:
    time.sleep(duracion)
    return threading.current_thread().name


def test_varias_solicitudes_se_procesan_concurrentemente() -> None:
    pool = PoolProcesamiento(4, nombre="prueba-worker")
    try:
        inicio = time.perf_counter()
        futuros = [pool.enviar(f"S{i}", _tarea, 0.2) for i in range(4)]
        hilos = {f.result() for f in futuros}
        transcurrido = time.perf_counter() - inicio
    finally:
        pool.apagar()

    # Cuatro tareas de 0.2 s en cuatro hilos deben tardar mucho menos que 0.8 s.
    assert transcurrido < 0.5, f"El procesamiento no fue concurrente ({transcurrido:.2f} s)"
    assert len(hilos) == 4, f"Se esperaban 4 hilos distintos, se usaron {hilos}"
    assert pool.estado()["pico_concurrencia"] == 4


def test_las_solicitudes_sobrantes_esperan_en_cola() -> None:
    """Cinco solicitudes con tres hilos: dos deben esperar (sección 8.5.1)."""
    pool = PoolProcesamiento(3, nombre="prueba-cola")
    try:
        futuros = [pool.enviar(f"S{i}", _tarea, 0.2) for i in range(5)]
        for f in futuros:
            f.result()
        mediciones = pool.mediciones()
        estado = pool.estado()
    finally:
        pool.apagar()

    assert estado["pico_concurrencia"] == 3, "Nunca deben trabajar más de 3 hilos a la vez"
    esperaron = [m for m in mediciones if m["espera_ms"] > 100]
    assert len(esperaron) == 2, f"Se esperaban 2 tareas en cola, hubo {len(esperaron)}"


def test_redimensionar_cambia_la_capacidad_sin_perder_tareas() -> None:
    pool = PoolProcesamiento(2, nombre="prueba-resize")
    try:
        assert pool.hilos == 2
        cambio = pool.redimensionar(6)
        assert cambio == {"hilos": 6, "anterior": 2, "cambio": True}

        futuros = [pool.enviar(f"S{i}", _tarea, 0.1) for i in range(6)]
        for f in futuros:
            f.result()

        assert pool.estado()["pico_concurrencia"] == 6
        assert pool.redimensionar(6)["cambio"] is False
    finally:
        pool.apagar()


def test_se_registran_las_metricas_de_cada_tarea() -> None:
    pool = PoolProcesamiento(2, nombre="prueba-metricas")
    try:
        pool.enviar("REF-1", _tarea, 0.05).result()
        medicion = pool.mediciones()[0]
    finally:
        pool.apagar()

    assert medicion["referencia"] == "REF-1"
    assert medicion["hilo"].startswith("prueba-metricas")
    assert medicion["procesamiento_ms"] >= 50
    assert medicion["exito"] is True


def test_un_error_no_detiene_el_pool() -> None:
    pool = PoolProcesamiento(2, nombre="prueba-error")

    def falla() -> None:
        raise ValueError("fallo simulado")

    try:
        futuro = pool.enviar("REF-ERROR", falla)
        try:
            futuro.result()
            raise AssertionError("Se esperaba que la tarea propagara el error")
        except ValueError:
            pass

        assert pool.enviar("REF-OK", _tarea, 0.02).result().startswith("prueba-error")
        estado = pool.estado()
    finally:
        pool.apagar()

    assert estado["total_fallidas"] == 1
    assert estado["total_procesadas"] == 2
