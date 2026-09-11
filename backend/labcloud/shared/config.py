"""Configuración central y registro de servicios/nodos de LabCloud Distributed.

Este módulo concentra el "mapa" de la arquitectura distribuida: qué servicios
existen, en qué nodo lógico viven y en qué puerto escucha cada proceso.

Referencia del diseño:
  - Tabla 7. Distribución de nodos
  - Tabla 8. Comunicación entre procesos (puertos de referencia)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.getenv("LABCLOUD_DATA_DIR", BASE_DIR / "data"))
HOST = os.getenv("LABCLOUD_HOST", "127.0.0.1")


@dataclass(frozen=True)
class NodeSpec:
    """Nodo lógico de ejecución. En el prototipo se simula con procesos y puertos."""

    id: str
    nombre: str
    responsabilidad: str


NODOS: dict[str, NodeSpec] = {
    "nodo-1": NodeSpec(
        id="nodo-1",
        nombre="Nodo 1 - Entrada y acceso",
        responsabilidad=(
            "Recibir las solicitudes de los usuarios, autenticarlas y dirigirlas "
            "hacia los servicios correspondientes."
        ),
    ),
    "nodo-2": NodeSpec(
        id="nodo-2",
        nombre="Nodo 2 - Procesamiento",
        responsabilidad=(
            "Procesar las solicitudes de análisis de manera concurrente mediante un "
            "conjunto controlado de hilos."
        ),
    ),
    "nodo-3": NodeSpec(
        id="nodo-3",
        nombre="Nodo 3 - Servicios de soporte",
        responsabilidad="Gestionar resultados y procesar los eventos de notificación.",
    ),
    "nodo-4": NodeSpec(
        id="nodo-4",
        nombre="Nodo 4 - Datos maestros",
        responsabilidad="Administrar la información de clientes y muestras del laboratorio.",
    ),
}


@dataclass(frozen=True)
class ServiceSpec:
    """Descripción de un servicio desplegable como proceso independiente."""

    id: str
    nombre: str
    modulo: str
    puerto: int
    nodo: str
    descripcion: str
    patrones: list[str] = field(default_factory=list)

    @property
    def base_url(self) -> str:
        return f"http://{HOST}:{self.puerto}"

    @property
    def db_path(self) -> Path:
        return DATA_DIR / f"{self.id}.db"


SERVICIOS: dict[str, ServiceSpec] = {
    "gateway": ServiceSpec(
        id="gateway",
        nombre="API Gateway",
        modulo="labcloud.gateway.main:app",
        puerto=int(os.getenv("PORT_GATEWAY", 8000)),
        nodo="nodo-1",
        descripcion="Punto de entrada único del sistema; direcciona las peticiones.",
        patrones=["Proxy"],
    ),
    "solicitudes": ServiceSpec(
        id="solicitudes",
        nombre="Servicio de Solicitudes",
        modulo="labcloud.services.solicitudes.main:app",
        puerto=int(os.getenv("PORT_SOLICITUDES", 8001)),
        nodo="nodo-2",
        descripcion="Gestiona y procesa concurrentemente las solicitudes de análisis.",
        patrones=["Mediator", "Thread Pool"],
    ),
    "resultados": ServiceSpec(
        id="resultados",
        nombre="Servicio de Resultados",
        modulo="labcloud.services.resultados.main:app",
        puerto=int(os.getenv("PORT_RESULTADOS", 8002)),
        nodo="nodo-3",
        descripcion="Registra y consulta resultados; publica el evento resultado.disponible.",
        patrones=["Observer distribuido (sujeto)"],
    ),
    "notificaciones": ServiceSpec(
        id="notificaciones",
        nombre="Servicio de Notificaciones",
        modulo="labcloud.services.notificaciones.main:app",
        puerto=int(os.getenv("PORT_NOTIFICACIONES", 8003)),
        nodo="nodo-3",
        descripcion="Recibe eventos y simula el envío de notificaciones al usuario.",
        patrones=["Observer distribuido (observador)"],
    ),
    "usuarios": ServiceSpec(
        id="usuarios",
        nombre="Servicio de Usuarios",
        modulo="labcloud.services.usuarios.main:app",
        puerto=int(os.getenv("PORT_USUARIOS", 8004)),
        nodo="nodo-1",
        descripcion="Administra usuarios, autenticación, roles y permisos.",
    ),
    "clientes": ServiceSpec(
        id="clientes",
        nombre="Servicio de Clientes",
        modulo="labcloud.services.clientes.main:app",
        puerto=int(os.getenv("PORT_CLIENTES", 8005)),
        nodo="nodo-4",
        descripcion="Registra y consulta la información de los clientes del laboratorio.",
    ),
    "muestras": ServiceSpec(
        id="muestras",
        nombre="Servicio de Muestras",
        modulo="labcloud.services.muestras.main:app",
        puerto=int(os.getenv("PORT_MUESTRAS", 8006)),
        nodo="nodo-4",
        descripcion="Administra las muestras recibidas y su información asociada.",
    ),
}

#: Orden de arranque: las dependencias primero, el gateway al final.
ORDEN_ARRANQUE = [
    "usuarios",
    "clientes",
    "muestras",
    "notificaciones",
    "resultados",
    "solicitudes",
    "gateway",
]


def servicio(service_id: str) -> ServiceSpec:
    try:
        return SERVICIOS[service_id]
    except KeyError as exc:  # pragma: no cover - error de configuración
        raise KeyError(f"Servicio desconocido: {service_id!r}") from exc


def url_de(service_id: str) -> str:
    """URL base de un servicio. Permite override por variable de entorno.

    Ejemplo: LABCLOUD_URL_RESULTADOS=http://10.0.0.5:8002 para un despliegue
    real en varias máquinas sin modificar el código.
    """
    env = os.getenv(f"LABCLOUD_URL_{service_id.upper()}")
    return env or servicio(service_id).base_url


# --- Parámetros de concurrencia (Servicio de Solicitudes) --------------------

#: Cantidad inicial de hilos del pool de procesamiento (configurable en caliente).
HILOS_INICIALES = int(os.getenv("LABCLOUD_HILOS", 4))

#: Duración simulada del análisis de laboratorio, en segundos.
DURACION_ANALISIS = float(os.getenv("LABCLOUD_DURACION_ANALISIS", 0.35))

#: Tiempos de espera para la comunicación HTTP entre servicios.
TIMEOUT_INTERNO = float(os.getenv("LABCLOUD_TIMEOUT", 15.0))
REINTENTOS_INTERNOS = int(os.getenv("LABCLOUD_REINTENTOS", 2))

#: Clave y algoritmo para los tokens de acceso emitidos por el Servicio de Usuarios.
JWT_SECRET = os.getenv("LABCLOUD_JWT_SECRET", "labcloud-distributed-demo-secret")
JWT_ALGORITHM = "HS256"
JWT_EXPIRA_MINUTOS = int(os.getenv("LABCLOUD_JWT_MINUTOS", 480))

#: Orígenes permitidos para el frontend Next.js.
CORS_ORIGINS = os.getenv(
    "LABCLOUD_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",")


def asegurar_directorio_datos() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR
