"""Patrón **Proxy** aplicado al acceso a los servicios distribuidos.

Cada servicio interno tiene aquí un *representante* local que expone la misma
interfaz que el servicio real (los mismos verbos y rutas HTTP) pero que vive en
el proceso del Gateway. El cliente conversa con el representante; este decide
si la petición procede, la reenvía por la red y devuelve la respuesta.

Lo que aporta el intermediario (sección 8.6.1 del diseño):

* El cliente no conoce la dirección ni el puerto del servicio real.
* Permite aplicar control de acceso y validación antes de tocar el servicio.
* Concentra la medición de latencia por servicio, base del análisis de cuellos
  de botella.
* Convierte la caída de un servicio en una respuesta 503 controlada, en lugar
  de un error de conexión sin contexto.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import httpx

from labcloud.shared.config import TIMEOUT_INTERNO, url_de

log = logging.getLogger("labcloud.proxy")

#: Encabezados que no deben reenviarse tal cual al servicio destino.
ENCABEZADOS_EXCLUIDOS = {
    "host",
    "content-length",
    "connection",
    "keep-alive",
    "transfer-encoding",
    "accept-encoding",
}


class EstadisticasProxy:
    """Contadores por servicio: peticiones, errores y latencia acumulada."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._datos: dict[str, dict[str, float]] = {}

    def registrar(self, servicio: str, ms: float, error: bool) -> None:
        with self._lock:
            fila = self._datos.setdefault(
                servicio, {"peticiones": 0, "errores": 0, "ms_total": 0.0, "ms_maximo": 0.0}
            )
            fila["peticiones"] += 1
            fila["ms_total"] += ms
            fila["ms_maximo"] = max(fila["ms_maximo"], ms)
            if error:
                fila["errores"] += 1

    def resumen(self) -> dict[str, dict[str, float]]:
        with self._lock:
            return {
                servicio: {
                    "peticiones": int(fila["peticiones"]),
                    "errores": int(fila["errores"]),
                    "latencia_promedio_ms": round(fila["ms_total"] / fila["peticiones"], 2)
                    if fila["peticiones"]
                    else 0.0,
                    "latencia_maxima_ms": round(fila["ms_maximo"], 2),
                }
                for servicio, fila in self._datos.items()
            }


class ProxyServicio:
    """Representante local de un servicio remoto."""

    def __init__(self, destino: str, estadisticas: EstadisticasProxy) -> None:
        self.destino = destino
        self._estadisticas = estadisticas
        self._cliente = httpx.AsyncClient(base_url=url_de(destino), timeout=TIMEOUT_INTERNO)

    async def cerrar(self) -> None:
        await self._cliente.aclose()

    async def reenviar(
        self,
        metodo: str,
        ruta: str,
        *,
        params: Any = None,
        contenido: bytes | None = None,
        encabezados: dict[str, str] | None = None,
    ) -> httpx.Response:
        """Reenvía la petición al servicio real y devuelve su respuesta."""
        inicio = time.perf_counter()
        try:
            respuesta = await self._cliente.request(
                metodo,
                ruta,
                params=params,
                content=contenido,
                headers=encabezados,
            )
        except httpx.HTTPError as exc:
            ms = (time.perf_counter() - inicio) * 1000
            self._estadisticas.registrar(self.destino, ms, error=True)
            log.error("%s %s%s -> sin respuesta (%s)", metodo, self.destino, ruta, exc)
            raise ServicioInalcanzable(self.destino, str(exc)) from exc

        ms = (time.perf_counter() - inicio) * 1000
        self._estadisticas.registrar(self.destino, ms, error=respuesta.status_code >= 500)
        log.info(
            "%s %s%s -> %s (%.1f ms)", metodo, self.destino, ruta, respuesta.status_code, ms
        )
        return respuesta

    async def salud(self) -> dict[str, Any]:
        """Consulta el ``/health`` del servicio real sin propagar excepciones."""
        try:
            respuesta = await self._cliente.get("/health", timeout=3.0)
            if respuesta.status_code < 400:
                return {**respuesta.json(), "alcanzable": True}
            return {
                "servicio": self.destino,
                "alcanzable": False,
                "estado": "degradado",
                "detalle": f"HTTP {respuesta.status_code}",
            }
        except httpx.HTTPError as exc:
            return {
                "servicio": self.destino,
                "alcanzable": False,
                "estado": "inactivo",
                "detalle": type(exc).__name__,
                "url": url_de(self.destino),
            }


class ServicioInalcanzable(RuntimeError):
    def __init__(self, servicio: str, detalle: str) -> None:
        super().__init__(f"El servicio '{servicio}' no respondió: {detalle}")
        self.servicio = servicio
        self.detalle = detalle


def filtrar_encabezados(encabezados: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in encabezados.items() if k.lower() not in ENCABEZADOS_EXCLUIDOS}
