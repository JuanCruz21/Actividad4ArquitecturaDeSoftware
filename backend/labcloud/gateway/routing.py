"""Tabla de enrutamiento del API Gateway.

Traduce las rutas públicas (``/api/...``) a la ruta interna del servicio que
debe atenderlas. Gracias a esta tabla el cliente nunca necesita conocer los
puertos ni las direcciones de los servicios internos: solo habla con el Gateway.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Ruta:
    prefijo_publico: str
    servicio: str
    prefijo_interno: str
    publico: bool = False
    descripcion: str = ""


RUTAS: tuple[Ruta, ...] = (
    Ruta("/api/auth", "usuarios", "/auth", publico=True, descripcion="Autenticación de usuarios"),
    Ruta("/api/usuarios", "usuarios", "/usuarios", descripcion="Gestión de usuarios y roles"),
    Ruta("/api/clientes", "clientes", "/clientes", descripcion="Clientes del laboratorio"),
    Ruta("/api/muestras", "muestras", "/muestras", descripcion="Muestras recibidas"),
    Ruta(
        "/api/solicitudes",
        "solicitudes",
        "/solicitudes",
        descripcion="Solicitudes de análisis (procesamiento concurrente)",
    ),
    Ruta(
        "/api/concurrencia",
        "solicitudes",
        "/concurrencia",
        descripcion="Configuración y estado del pool de hilos",
    ),
    Ruta("/api/pruebas", "solicitudes", "/pruebas", descripcion="Pruebas de carga y comparativas"),
    Ruta("/api/resultados", "resultados", "/resultados", descripcion="Resultados de análisis"),
    Ruta(
        "/api/eventos",
        "resultados",
        "/eventos",
        descripcion="Observer distribuido: suscripciones y bitácora de eventos",
    ),
    Ruta(
        "/api/notificaciones",
        "notificaciones",
        "/notificaciones",
        descripcion="Notificaciones generadas a partir de eventos",
    ),
    Ruta(
        "/api/simulacion",
        "notificaciones",
        "/simulacion",
        descripcion="Simulación de caída de un servicio secundario",
    ),
)


def resolver(camino: str) -> tuple[Ruta, str] | None:
    """Devuelve la ruta de la tabla y el camino interno para una URL pública.

    Se evalúa de la más específica a la más general para que, por ejemplo,
    ``/api/solicitudes`` no capture peticiones de ``/api/solicitudes-x``.
    """
    for ruta in sorted(RUTAS, key=lambda r: len(r.prefijo_publico), reverse=True):
        if camino == ruta.prefijo_publico or camino.startswith(ruta.prefijo_publico + "/"):
            resto = camino[len(ruta.prefijo_publico) :]
            return ruta, f"{ruta.prefijo_interno}{resto}"
    return None
