"""Banco de pruebas de concurrencia y escalabilidad (capítulo 10 del diseño).

Permite lanzar N solicitudes contra el pool con una cantidad determinada de
hilos y registrar tiempo total, throughput, latencias y pico de concurrencia,
para comparar configuraciones de 1, 2, 4 y 8 hilos (RF09, RF10).

Dos modos:

* ``aislar_pool=True``  → cada tarea ejecuta únicamente el análisis simulado.
  Mide el comportamiento puro de la concurrencia, sin ruido de la red.
* ``aislar_pool=False`` → cada tarea recorre el flujo completo a través del
  Mediator (Muestras → Resultados → evento). Mide el sistema distribuido real.
"""

from __future__ import annotations

import logging
import statistics
import time
from concurrent.futures import Future
from typing import Any

from labcloud.services.solicitudes.analisis import ejecutar_analisis
from labcloud.services.solicitudes.mediator import MediadorAnalisis
from labcloud.services.solicitudes.pool import PoolProcesamiento
from labcloud.shared.config import DURACION_ANALISIS
from labcloud.shared.schemas import nuevo_id

log = logging.getLogger("labcloud.pruebas")


def _percentil(valores: list[float], porcentaje: float) -> float:
    if not valores:
        return 0.0
    ordenados = sorted(valores)
    indice = min(len(ordenados) - 1, int(round((porcentaje / 100) * len(ordenados) + 0.5)) - 1)
    return ordenados[max(0, indice)]


def ejecutar_prueba(
    pool: PoolProcesamiento,
    mediador: MediadorAnalisis,
    *,
    solicitudes: int,
    hilos: int | None,
    duracion_analisis_s: float | None,
    aislar_pool: bool,
    etiqueta: str = "",
    contexto: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Lanza la carga y devuelve las métricas de la corrida."""
    hilos_previos = pool.hilos
    if hilos and hilos != hilos_previos:
        pool.redimensionar(hilos)

    duracion = DURACION_ANALISIS if duracion_analisis_s is None else duracion_analisis_s
    corrida = nuevo_id()[:8]
    prefijo = f"PRUEBA-{corrida}"
    tipo_analisis = (contexto or {}).get("tipo_analisis", "hemograma")

    def tarea_aislada(indice: int) -> dict[str, Any]:
        _, diagnostico, ms = ejecutar_analisis(tipo_analisis, duracion_s=duracion)
        return {"indice": indice, "diagnostico": diagnostico, "duracion_ms": ms}

    def tarea_completa(indice: int) -> dict[str, Any]:
        datos = dict(contexto or {})
        datos["solicitud_id"] = f"{prefijo}-{indice}"
        datos["codigo"] = f"{prefijo}-{indice}"
        datos.setdefault("tipo_analisis", tipo_analisis)
        return mediador.procesar(datos, duracion_analisis_s=duracion)

    tarea = tarea_aislada if aislar_pool else tarea_completa

    log.info(
        "Iniciando prueba %s: %d solicitudes, %d hilos, análisis de %.2f s (%s)",
        corrida,
        solicitudes,
        pool.hilos,
        duracion,
        "pool aislado" if aislar_pool else "flujo distribuido completo",
    )

    inicio = time.perf_counter()
    futuros: list[Future] = [
        pool.enviar(f"{prefijo}#{i + 1}", tarea, i + 1) for i in range(solicitudes)
    ]

    exitosas, fallidas, errores = 0, 0, []
    for futuro in futuros:
        try:
            futuro.result()
            exitosas += 1
        except Exception as exc:
            fallidas += 1
            if len(errores) < 5:
                errores.append(f"{type(exc).__name__}: {exc}")
    tiempo_total = time.perf_counter() - inicio

    mediciones = [
        m for m in pool.mediciones(limite=1000) if m["referencia"].startswith(prefijo)
    ]
    latencias = [m["total_ms"] for m in mediciones]
    esperas = [m["espera_ms"] for m in mediciones]
    hilos_usados = sorted({m["hilo"] for m in mediciones})
    pico = max((m["concurrencia_observada"] for m in mediciones), default=0)

    resumen = {
        "corrida": corrida,
        "etiqueta": etiqueta or f"{solicitudes} solicitudes / {pool.hilos} hilos",
        "solicitudes": solicitudes,
        "hilos": pool.hilos,
        "duracion_analisis_s": duracion,
        "tiempo_total_s": round(tiempo_total, 4),
        "throughput_rps": round(solicitudes / tiempo_total, 2) if tiempo_total else 0.0,
        "latencia_promedio_ms": round(statistics.fmean(latencias), 2) if latencias else 0.0,
        "latencia_p95_ms": round(_percentil(latencias, 95), 2),
        "latencia_maxima_ms": round(max(latencias), 2) if latencias else 0.0,
        "espera_promedio_ms": round(statistics.fmean(esperas), 2) if esperas else 0.0,
        "exitosas": exitosas,
        "fallidas": fallidas,
        "pico_concurrencia": pico,
        "hilos_utilizados": hilos_usados,
        "detalle": {
            "modo": "pool_aislado" if aislar_pool else "flujo_distribuido",
            "tiempo_secuencial_estimado_s": round(solicitudes * duracion, 4),
            "aceleracion": (
                round((solicitudes * duracion) / tiempo_total, 2) if tiempo_total else 0.0
            ),
            "eficiencia_por_hilo": (
                round(((solicitudes * duracion) / tiempo_total) / pool.hilos, 2)
                if tiempo_total and pool.hilos
                else 0.0
            ),
            "errores": errores,
        },
    }

    log.info(
        "Prueba %s finalizada: %.3f s totales | %.2f sol/s | aceleración x%.2f | hilos usados: %d",
        corrida,
        resumen["tiempo_total_s"],
        resumen["throughput_rps"],
        resumen["detalle"]["aceleracion"],
        len(hilos_usados),
    )
    return resumen


def ejecutar_comparativa(
    pool: PoolProcesamiento,
    mediador: MediadorAnalisis,
    *,
    solicitudes: int,
    configuraciones: list[int],
    duracion_analisis_s: float | None,
    aislar_pool: bool,
    contexto: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Repite la misma carga con varias cantidades de hilos y compara.

    Es la prueba que sustenta el análisis de escalabilidad y la identificación
    del punto a partir del cual agregar hilos deja de aportar (sección 8.5.4).
    """
    hilos_originales = pool.hilos
    corridas: list[dict[str, Any]] = []
    try:
        for hilos in configuraciones:
            corridas.append(
                ejecutar_prueba(
                    pool,
                    mediador,
                    solicitudes=solicitudes,
                    hilos=hilos,
                    duracion_analisis_s=duracion_analisis_s,
                    aislar_pool=aislar_pool,
                    etiqueta=f"{hilos} hilo(s)",
                    contexto=contexto,
                )
            )
    finally:
        pool.redimensionar(hilos_originales)

    base = corridas[0]["tiempo_total_s"] if corridas else 0.0
    for corrida in corridas:
        corrida["detalle"]["mejora_vs_primera"] = (
            round(base / corrida["tiempo_total_s"], 2) if corrida["tiempo_total_s"] else 0.0
        )

    mejor = min(corridas, key=lambda c: c["tiempo_total_s"]) if corridas else None
    return {
        "solicitudes": solicitudes,
        "configuraciones": configuraciones,
        "modo": "pool_aislado" if aislar_pool else "flujo_distribuido",
        "corridas": corridas,
        "mejor_configuracion": mejor["hilos"] if mejor else None,
        "conclusion": _interpretar(corridas),
    }


def _interpretar(corridas: list[dict[str, Any]]) -> str:
    """Genera una lectura en texto de la comparativa, para la documentación.

    Además del mejor tiempo, informa sobre la **eficiencia por hilo**: el tiempo
    total puede seguir bajando mientras cada hilo aporta cada vez menos. Ese es
    el rendimiento decreciente que describe la sección 8.5.4 del diseño, y no se
    ve mirando solo el tiempo.
    """
    if len(corridas) < 2:
        return "Se requiere más de una configuración para comparar."

    mejor = min(corridas, key=lambda c: c["tiempo_total_s"])
    primera, ultima = corridas[0], corridas[-1]
    texto = (
        f"Con {primera['solicitudes']} solicitudes, el mejor tiempo se obtuvo con "
        f"{mejor['hilos']} hilo(s): {mejor['tiempo_total_s']} s "
        f"({mejor['throughput_rps']} solicitudes/s)."
    )

    if mejor is not ultima and ultima["hilos"] > mejor["hilos"]:
        texto += (
            f" Pasar a {ultima['hilos']} hilos no mejoró el tiempo "
            f"({ultima['tiempo_total_s']} s): a partir de ese punto el exceso de hilos "
            "solo añade competencia por los recursos."
        )
        return texto

    # El tiempo siguió bajando: hay que mirar cuánto aporta cada hilo adicional.
    eficiencia_inicial = primera["detalle"]["eficiencia_por_hilo"]
    eficiencia_final = ultima["detalle"]["eficiencia_por_hilo"]
    caida = (
        round((1 - eficiencia_final / eficiencia_inicial) * 100)
        if eficiencia_inicial
        else 0
    )

    if caida >= 15:
        texto += (
            f" El tiempo total siguió bajando, pero la eficiencia por hilo cayó de "
            f"{eficiencia_inicial} a {eficiencia_final} ({caida} % menos): cada hilo "
            "adicional aporta cada vez menos, que es el rendimiento decreciente "
            "esperado al sobrepasar la capacidad real de procesamiento."
        )
    else:
        texto += (
            f" La eficiencia por hilo se mantuvo alta ({eficiencia_inicial} → "
            f"{eficiencia_final}), así que con esta carga el sistema todavía tiene "
            "margen de concurrencia."
        )

    # Señal adicional: cuánto rindió el último salto frente al anterior.
    if len(corridas) >= 3:
        anterior = corridas[-2]
        if anterior["tiempo_total_s"]:
            ganancia = ultima["throughput_rps"] / anterior["throughput_rps"]
            factor = ultima["hilos"] / anterior["hilos"]
            if ganancia < factor * 0.8:
                texto += (
                    f" De hecho, duplicar de {anterior['hilos']} a {ultima['hilos']} hilos "
                    f"solo multiplicó el throughput por {round(ganancia, 2)} en lugar de "
                    f"por {round(factor, 2)}."
                )
    return texto
