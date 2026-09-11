"""Simulación del trabajo de laboratorio.

Representa el tiempo y el esfuerzo que toma procesar una muestra. Es el
fragmento de código que realmente se ejecuta dentro de cada hilo del pool, y su
duración es configurable para poder observar el efecto de la concurrencia sobre
el tiempo total de atención.
"""

from __future__ import annotations

import random
import time
from typing import Any

from labcloud.shared.config import DURACION_ANALISIS

#: Rangos de referencia por tipo de análisis: (nombre, mínimo, máximo, unidad).
PARAMETROS: dict[str, list[tuple[str, float, float, str]]] = {
    "hemograma": [
        ("hemoglobina", 12.0, 17.5, "g/dL"),
        ("hematocrito", 36.0, 52.0, "%"),
        ("leucocitos", 4.0, 11.0, "10^3/uL"),
        ("plaquetas", 150.0, 450.0, "10^3/uL"),
    ],
    "perfil_lipidico": [
        ("colesterol_total", 120.0, 240.0, "mg/dL"),
        ("hdl", 35.0, 80.0, "mg/dL"),
        ("ldl", 60.0, 190.0, "mg/dL"),
        ("trigliceridos", 60.0, 220.0, "mg/dL"),
    ],
    "glucosa": [("glucosa_ayunas", 65.0, 135.0, "mg/dL")],
    "uroanalisis": [
        ("ph", 4.5, 8.0, ""),
        ("densidad", 1.005, 1.030, ""),
        ("leucocitos_campo", 0.0, 12.0, "/campo"),
    ],
    "cultivo": [("ufc", 0.0, 100000.0, "UFC/mL")],
    "covid19": [("carga_viral_ct", 15.0, 40.0, "Ct")],
    "general": [("indice_general", 0.0, 100.0, "")],
}

#: Umbrales a partir de los cuales el valor se considera fuera de rango.
LIMITES_ALERTA = {
    "hemoglobina": 16.0,
    "colesterol_total": 200.0,
    "glucosa_ayunas": 100.0,
    "leucocitos": 10.0,
    "ufc": 50000.0,
    "carga_viral_ct": 30.0,
}


def ejecutar_analisis(
    tipo: str, *, duracion_s: float | None = None
) -> tuple[dict[str, Any], str, float]:
    """Procesa una muestra y devuelve ``(valores, diagnóstico, duración_ms)``.

    La espera usa ``time.sleep``, que libera el GIL: por eso varios hilos
    avanzan de verdad en paralelo, igual que ocurriría con operaciones de
    entrada/salida o llamadas de red reales.
    """
    duracion = DURACION_ANALISIS if duracion_s is None else duracion_s
    inicio = time.perf_counter()

    parametros = PARAMETROS.get(tipo, PARAMETROS["general"])
    if duracion > 0:
        time.sleep(duracion)

    valores: dict[str, Any] = {}
    alertas: list[str] = []
    for nombre, minimo, maximo, unidad in parametros:
        valor = round(random.uniform(minimo, maximo), 2)
        valores[nombre] = {"valor": valor, "unidad": unidad, "rango": f"{minimo} - {maximo}"}
        umbral = LIMITES_ALERTA.get(nombre)
        if umbral is not None and valor > umbral:
            alertas.append(nombre)

    diagnostico = (
        f"Valores alterados en: {', '.join(alertas)}"
        if alertas
        else "Dentro de parámetros normales"
    )
    return valores, diagnostico, (time.perf_counter() - inicio) * 1000
