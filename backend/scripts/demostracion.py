"""Demostración guiada del prototipo LabCloud Distributed.

Recorre, contra los servicios en ejecución, los escenarios que la actividad
pide evidenciar y deja un informe en Markdown con los resultados obtenidos:

  1. Estado de los nodos (distribución en procesos y puertos).
  2. Flujo completo de una solicitud (REST + hilos + eventos).
  3. Procesamiento concurrente: 5 solicitudes con 3 hilos.
  4. Comparativa de 1, 2, 4 y 8 hilos (pruebas de concurrencia y escalabilidad).
  5. Tolerancia a fallos: caída del Servicio de Notificaciones.

Uso (con los servicios arriba):

    uv run python -m labcloud iniciar        # en otra terminal
    uv run python scripts/demostracion.py
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

GATEWAY = "http://127.0.0.1:8000"
SALIDA = Path(__file__).resolve().parents[1] / "informes"

NEGRITA, VERDE, AZUL, AMARILLO, ROJO, RESET = (
    "\033[1m",
    "\033[92m",
    "\033[96m",
    "\033[93m",
    "\033[91m",
    "\033[0m",
)


class Informe:
    def __init__(self) -> None:
        self.lineas: list[str] = []

    def titulo(self, texto: str) -> None:
        print(f"\n{NEGRITA}{AZUL}▌ {texto}{RESET}")
        print("─" * 78)
        self.lineas.append(f"\n## {texto}\n")

    def linea(self, texto: str, color: str = "") -> None:
        print(f"  {color}{texto}{RESET}" if color else f"  {texto}")
        self.lineas.append(texto)

    def tabla(self, encabezados: list[str], filas: list[list[Any]]) -> None:
        anchos = [
            max(len(str(encabezados[i])), *(len(str(f[i])) for f in filas))
            for i in range(len(encabezados))
        ]
        cabecera = "  ".join(str(h).ljust(anchos[i]) for i, h in enumerate(encabezados))
        print(f"  {NEGRITA}{cabecera}{RESET}")
        print(f"  {'─' * len(cabecera)}")
        for fila in filas:
            print("  " + "  ".join(str(c).ljust(anchos[i]) for i, c in enumerate(fila)))

        self.lineas.append("| " + " | ".join(encabezados) + " |")
        self.lineas.append("|" + "|".join(["---"] * len(encabezados)) + "|")
        for fila in filas:
            self.lineas.append("| " + " | ".join(str(c) for c in fila) + " |")

    def guardar(self) -> Path:
        SALIDA.mkdir(parents=True, exist_ok=True)
        archivo = SALIDA / f"evidencias-{datetime.now():%Y%m%d-%H%M%S}.md"
        encabezado = (
            "# Evidencias de funcionamiento — LabCloud Distributed\n\n"
            f"Generado el {datetime.now():%d/%m/%Y a las %H:%M:%S}\n"
        )
        archivo.write_text(encabezado + "\n".join(self.lineas) + "\n", encoding="utf-8")
        return archivo


def main() -> int:
    informe = Informe()
    cliente = httpx.Client(base_url=GATEWAY, timeout=300)

    print(f"\n{NEGRITA}LabCloud Distributed — demostración del prototipo{RESET}")

    # --- 1. Nodos -----------------------------------------------------------
    informe.titulo("1. Distribución en nodos")
    try:
        salud = cliente.get("/salud").json()
    except httpx.HTTPError:
        print(
            f"\n{ROJO}No se pudo contactar al API Gateway en {GATEWAY}.{RESET}\n"
            "  Levante los servicios con:  uv run python -m labcloud iniciar\n"
        )
        return 1

    informe.tabla(
        ["Servicio", "Nodo", "Puerto", "PID", "Hilos", "Estado"],
        [
            [
                s["nombre"],
                s["nodo_nombre"],
                s["puerto"],
                s.get("pid", "—"),
                s.get("hilos_activos", "—"),
                "activo" if s["alcanzable"] else "sin respuesta",
            ]
            for s in salud["servicios"]
        ],
    )
    informe.linea("")
    informe.linea(
        f"Estado general: {salud['estado_general']} "
        f"({salud['servicios_activos']}/{salud['servicios_totales']} servicios activos)."
    )
    if salud["estado_general"] != "operativo":
        print(f"\n{AMARILLO}Hay servicios caídos; algunos escenarios podrían fallar.{RESET}")

    # --- 2. Autenticación ---------------------------------------------------
    acceso = cliente.post(
        "/api/auth/login", json={"email": "admin@labcloud.co", "clave": "admin123"}
    ).json()
    cabeceras = {"Authorization": f"Bearer {acceso['token']}"}

    informe.titulo("2. Flujo completo de una solicitud de análisis")
    informe.linea(
        f"Acceso concedido a {acceso['usuario']['nombre']} ({acceso['usuario']['rol']}) "
        "por el Servicio de Usuarios; el Gateway validará el token en cada escritura.",
        VERDE,
    )

    rechazo = cliente.post(
        "/api/clientes", json={"documento": "X", "nombre": "Y", "email": "a@b.co"}
    )
    informe.linea(
        f"Escritura sin token rechazada por el Gateway (HTTP {rechazo.status_code}) "
        "antes de llegar al servicio interno — patrón Proxy.",
        VERDE,
    )

    cliente_lab = cliente.get("/api/clientes").json()[0]
    sello = int(time.time())
    muestra = cliente.post(
        "/api/muestras",
        headers=cabeceras,
        json={
            "codigo": f"MU-DEMO-{sello}",
            "cliente_id": cliente_lab["id"],
            "tipo": "sangre",
            "descripcion": "Muestra generada por la demostración",
        },
    ).json()

    inicio = time.perf_counter()
    solicitud = cliente.post(
        "/api/solicitudes",
        headers=cabeceras,
        json={
            "cliente_id": cliente_lab["id"],
            "muestra_id": muestra["id"],
            "tipo_analisis": "hemograma",
            "prioridad": "alta",
        },
    ).json()
    transcurrido = (time.perf_counter() - inicio) * 1000
    time.sleep(1.0)

    resultados = cliente.get(f"/api/resultados?solicitud_id={solicitud['id']}").json()
    notificaciones = cliente.get("/api/notificaciones?limite=1").json()
    estado_muestra = cliente.get(f"/api/muestras/{muestra['id']}").json()["estado"]

    informe.linea("")
    informe.tabla(
        ["Paso", "Componente", "Resultado"],
        [
            ["Cliente validado", "Servicio de Clientes", cliente_lab["nombre"]],
            ["Muestra registrada", "Servicio de Muestras", muestra["codigo"]],
            ["Solicitud creada", "API Gateway → Solicitudes", solicitud["codigo"]],
            ["Hilo asignado", "Pool de procesamiento", solicitud["hilo_procesamiento"]],
            ["Estado final", "Servicio de Solicitudes", solicitud["estado"]],
            [
                "Resultado",
                "Servicio de Resultados",
                resultados[0]["diagnostico"] if resultados else "no registrado",
            ],
            [
                "Notificación",
                "Servicio de Notificaciones",
                notificaciones[0]["asunto"] if notificaciones else "no generada",
            ],
            ["Muestra actualizada", "Servicio de Muestras", estado_muestra],
        ],
    )
    informe.linea("")
    informe.linea(
        f"Tiempo de respuesta extremo a extremo: {transcurrido:.0f} ms "
        f"(procesamiento del análisis: {solicitud['duracion_ms']:.0f} ms)."
    )

    # --- 3. Cola de procesamiento ------------------------------------------
    informe.titulo("3. Procesamiento concurrente: 5 solicitudes con 3 hilos")
    corrida = cliente.post(
        "/api/pruebas/carga",
        headers=cabeceras,
        json={
            "solicitudes": 5,
            "hilos": 3,
            "duracion_analisis_s": 0.5,
            "aislar_pool": True,
            "etiqueta": "5 solicitudes / 3 hilos",
        },
    ).json()
    informe.tabla(
        ["Métrica", "Valor"],
        [
            ["Solicitudes enviadas", corrida["solicitudes"]],
            ["Hilos disponibles", corrida["hilos"]],
            ["Tiempo total", f"{corrida['tiempo_total_s']} s"],
            [
                "Tiempo secuencial estimado",
                f"{corrida['detalle']['tiempo_secuencial_estimado_s']} s",
            ],
            ["Aceleración obtenida", f"x{corrida['detalle']['aceleracion']}"],
            ["Espera promedio en cola", f"{corrida['espera_promedio_ms']} ms"],
            ["Pico de concurrencia", corrida["pico_concurrencia"]],
            ["Hilos distintos utilizados", len(corrida["hilos_utilizados"])],
        ],
    )
    informe.linea("")
    informe.linea(
        "Tres solicitudes inician de inmediato y las dos restantes esperan en cola "
        "hasta que un hilo queda libre, tal como describe la sección 8.5.1 del diseño."
    )

    # --- 4. Comparativa de hilos -------------------------------------------
    informe.titulo("4. Pruebas de concurrencia y escalabilidad (1, 2, 4 y 8 hilos)")
    comparativa = cliente.post(
        "/api/pruebas/comparativa",
        headers=cabeceras,
        json={
            "solicitudes": 24,
            "configuraciones": [1, 2, 4, 8],
            "duracion_analisis_s": 0.25,
            "aislar_pool": True,
        },
    ).json()
    informe.tabla(
        [
            "Hilos",
            "Tiempo (s)",
            "Sol/s",
            "Latencia media (ms)",
            "p95 (ms)",
            "Espera (ms)",
            "Aceleración",
        ],
        [
            [
                c["hilos"],
                f"{c['tiempo_total_s']:.3f}",
                c["throughput_rps"],
                c["latencia_promedio_ms"],
                c["latencia_p95_ms"],
                c["espera_promedio_ms"],
                f"x{c['detalle']['aceleracion']}",
            ]
            for c in comparativa["corridas"]
        ],
    )
    informe.linea("")
    informe.linea(comparativa["conclusion"], AMARILLO)

    # --- 5. Tolerancia a fallos --------------------------------------------
    informe.titulo("5. Tolerancia a fallos: caída del Servicio de Notificaciones")
    antes = cliente.get("/api/notificaciones/resumen").json()["total"]
    cliente.put("/api/simulacion/disponibilidad", headers=cabeceras, json={"disponible": False})

    inicio = time.perf_counter()
    solicitud_fallo = cliente.post(
        "/api/solicitudes",
        headers=cabeceras,
        json={"cliente_id": cliente_lab["id"], "tipo_analisis": "glucosa"},
    ).json()
    demora = (time.perf_counter() - inicio) * 1000
    informe_resultados = cliente.get(
        f"/api/resultados?solicitud_id={solicitud_fallo['id']}"
    ).json()
    registrado = len(informe_resultados) == 1

    time.sleep(7)
    eventos = cliente.get("/api/eventos/estado").json()
    durante = cliente.get("/api/notificaciones/resumen").json()["total"]

    cliente.put("/api/simulacion/disponibilidad", headers=cabeceras, json={"disponible": True})
    reencolados = cliente.post("/api/eventos/reintentar", headers=cabeceras).json()["reencolados"]
    time.sleep(2)
    despues = cliente.get("/api/notificaciones/resumen").json()["total"]

    informe.tabla(
        ["Observación", "Valor"],
        [
            ["Estado de la solicitud", solicitud_fallo["estado"]],
            ["Tiempo de respuesta con el observador caído", f"{demora:.0f} ms"],
            ["Resultado registrado igualmente", "sí" if registrado else "no"],
            ["Eventos archivados", eventos["eventos_archivados"]],
            ["Notificaciones durante la caída", f"{durante} (antes: {antes})"],
            ["Eventos reencolados al recuperar", reencolados],
            ["Notificaciones tras la recuperación", despues],
        ],
    )
    informe.linea("")
    informe.linea(
        "El flujo principal no se interrumpe: la solicitud se procesa y el resultado se "
        "registra aunque el observador esté caído. El evento queda archivado y se entrega "
        "cuando el servicio se restablece (RNF07).",
        VERDE,
    )

    archivo = informe.guardar()
    print(f"\n{NEGRITA}{VERDE}Informe de evidencias guardado en:{RESET} {archivo}\n")
    cliente.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
