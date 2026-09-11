"""Orquestador de procesos de LabCloud Distributed.

Levanta cada servicio como un **proceso independiente** escuchando en su propio
puerto, que es la forma en que el prototipo simula los nodos de la arquitectura
(sección 8.2: "Consideración sobre la simulación de nodos").

Uso:

    uv run labcloud iniciar                 # levanta todos los servicios
    uv run labcloud iniciar --solo gateway solicitudes resultados
    uv run labcloud servicio solicitudes    # un único servicio en primer plano
    uv run labcloud estado                  # consulta la salud de cada nodo
    uv run labcloud arquitectura            # imprime la topología
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
import time
from typing import IO

import httpx

from labcloud.shared.config import (
    BASE_DIR,
    HOST,
    NODOS,
    ORDEN_ARRANQUE,
    SERVICIOS,
    asegurar_directorio_datos,
    servicio,
    url_de,
)


def _entorno_hijo() -> dict[str, str]:
    """Entorno de los procesos hijos.

    Se fija ``PYTHONPATH`` a la raíz del backend para que cada servicio pueda
    importar el paquete ``labcloud`` sin depender del directorio de trabajo.
    """
    entorno = dict(os.environ)
    entorno["PYTHONUNBUFFERED"] = "1"
    raiz = str(BASE_DIR)
    previo = entorno.get("PYTHONPATH", "")
    entorno["PYTHONPATH"] = f"{raiz}{os.pathsep}{previo}" if previo else raiz
    return entorno


COLORES = {
    "gateway": "\033[95m",
    "solicitudes": "\033[96m",
    "resultados": "\033[92m",
    "notificaciones": "\033[93m",
    "usuarios": "\033[94m",
    "clientes": "\033[35m",
    "muestras": "\033[36m",
}
RESET = "\033[0m"
NEGRITA = "\033[1m"


def _comando(service_id: str, recargar: bool) -> list[str]:
    spec = servicio(service_id)
    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        spec.modulo,
        "--host",
        HOST,
        "--port",
        str(spec.puerto),
        "--log-level",
        os.getenv("LABCLOUD_LOG_LEVEL", "info").lower(),
    ]
    if recargar:
        cmd += ["--reload", "--reload-dir", "labcloud"]
    return cmd


def _volcar_salida(flujo: IO[str], service_id: str) -> None:
    color = COLORES.get(service_id, "")
    etiqueta = f"{color}[{service_id:<14}]{RESET}"
    for linea in iter(flujo.readline, ""):
        sys.stdout.write(f"{etiqueta} {linea}")
        sys.stdout.flush()


def iniciar(ids: list[str], *, recargar: bool = False, esperar: bool = True) -> int:
    asegurar_directorio_datos()
    procesos: list[tuple[str, subprocess.Popen]] = []

    print(f"\n{NEGRITA}LabCloud Distributed — arranque de nodos{RESET}")
    print("=" * 78)
    for service_id in ids:
        spec = servicio(service_id)
        nodo = NODOS[spec.nodo]
        proceso = subprocess.Popen(
            _comando(service_id, recargar),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            env=_entorno_hijo(),
        )
        procesos.append((service_id, proceso))
        threading.Thread(
            target=_volcar_salida,
            args=(proceso.stdout, service_id),
            name=f"salida-{service_id}",
            daemon=True,
        ).start()
        color = COLORES.get(service_id, "")
        print(
            f"  {color}●{RESET} {spec.nombre:<26} {nodo.nombre:<28} "
            f"puerto {spec.puerto}  pid {proceso.pid}"
        )
        # Pequeña pausa para que las dependencias estén listas antes del siguiente.
        time.sleep(0.6)

    print("=" * 78)
    print(f"  Panel de servicios : {url_de('gateway')}/docs")
    print(f"  Salud del sistema  : {url_de('gateway')}/salud")
    print(f"  Arquitectura       : {url_de('gateway')}/arquitectura")
    print("\n  Ctrl+C para detener todos los nodos.\n")

    if not esperar:
        return 0

    def _detener(*_args: object) -> None:
        print(f"\n{NEGRITA}Deteniendo nodos...{RESET}")
        for _service_id, proceso in reversed(procesos):
            if proceso.poll() is None:
                proceso.terminate()
        for service_id, proceso in reversed(procesos):
            try:
                proceso.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proceso.kill()
            print(f"  ○ {servicio(service_id).nombre} detenido")
        sys.exit(0)

    signal.signal(signal.SIGINT, _detener)
    signal.signal(signal.SIGTERM, _detener)

    try:
        while True:
            for service_id, proceso in procesos:
                codigo = proceso.poll()
                if codigo is not None:
                    print(
                        f"\n[!] El servicio '{service_id}' terminó con código {codigo}. "
                        "Deteniendo el resto."
                    )
                    _detener()
            time.sleep(0.5)
    except KeyboardInterrupt:  # pragma: no cover
        _detener()
    return 0


def ejecutar_uno(service_id: str, recargar: bool) -> int:
    asegurar_directorio_datos()
    return subprocess.call(_comando(service_id, recargar), env=_entorno_hijo())


def estado() -> int:
    print(f"\n{NEGRITA}Estado de los nodos de LabCloud Distributed{RESET}")
    print("=" * 78)
    activos = 0
    for service_id in ORDEN_ARRANQUE:
        spec = SERVICIOS[service_id]
        try:
            respuesta = httpx.get(f"{url_de(service_id)}/health", timeout=3.0)
            datos = respuesta.json()
            activos += 1
            print(
                f"  \033[92m●\033[0m {spec.nombre:<26} {NODOS[spec.nodo].nombre:<28} "
                f":{spec.puerto}  pid {datos['pid']}  hilos {datos['hilos_activos']}"
            )
        except httpx.HTTPError:
            print(
                f"  \033[91m○\033[0m {spec.nombre:<26} {NODOS[spec.nodo].nombre:<28} "
                f":{spec.puerto}  no responde"
            )
    print("=" * 78)
    print(f"  {activos}/{len(ORDEN_ARRANQUE)} servicios activos\n")
    return 0 if activos == len(ORDEN_ARRANQUE) else 1


def arquitectura() -> int:
    print(f"\n{NEGRITA}Topología de LabCloud Distributed{RESET}")
    print("=" * 78)
    for nodo in NODOS.values():
        print(f"\n  {NEGRITA}{nodo.nombre}{RESET}")
        print(f"    {nodo.responsabilidad}")
        for spec in SERVICIOS.values():
            if spec.nodo != nodo.id:
                continue
            patrones = f"  [{', '.join(spec.patrones)}]" if spec.patrones else ""
            print(f"      · {spec.nombre:<26} :{spec.puerto}{patrones}")
    print("\n" + "=" * 78 + "\n")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="labcloud", description="Orquestador del prototipo LabCloud Distributed"
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_iniciar = sub.add_parser("iniciar", help="Levanta los servicios como procesos separados")
    p_iniciar.add_argument("--solo", nargs="+", metavar="SERVICIO", help="Servicios a levantar")
    p_iniciar.add_argument(
        "--recargar", action="store_true", help="Recarga automática (desarrollo)"
    )

    p_uno = sub.add_parser("servicio", help="Ejecuta un único servicio en primer plano")
    p_uno.add_argument("nombre", choices=sorted(SERVICIOS))
    p_uno.add_argument("--recargar", action="store_true")

    sub.add_parser("estado", help="Consulta la salud de cada nodo")
    sub.add_parser("arquitectura", help="Imprime la topología del sistema")

    args = parser.parse_args()

    if args.comando == "iniciar":
        ids = args.solo or ORDEN_ARRANQUE
        desconocidos = [s for s in ids if s not in SERVICIOS]
        if desconocidos:
            parser.error(f"Servicios desconocidos: {', '.join(desconocidos)}")
        ordenados = [s for s in ORDEN_ARRANQUE if s in ids]
        return iniciar(ordenados, recargar=args.recargar)
    if args.comando == "servicio":
        return ejecutar_uno(args.nombre, args.recargar)
    if args.comando == "estado":
        return estado()
    if args.comando == "arquitectura":
        return arquitectura()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
