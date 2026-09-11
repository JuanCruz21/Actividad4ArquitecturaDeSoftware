"""Cliente HTTP para la comunicación síncrona entre servicios (REST).

Todas las llamadas entre nodos pasan por aquí, lo que permite aplicar de forma
uniforme tiempos de espera y reintentos, y registrar la latencia de cada salto
de red para el análisis de cuellos de botella (RNF05).
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from labcloud.shared.config import REINTENTOS_INTERNOS, TIMEOUT_INTERNO, url_de

log = logging.getLogger("labcloud.http")


class ServicioNoDisponible(RuntimeError):
    """El servicio destino no respondió tras agotar los reintentos."""

    def __init__(self, servicio: str, detalle: str) -> None:
        super().__init__(f"Servicio '{servicio}' no disponible: {detalle}")
        self.servicio = servicio
        self.detalle = detalle


class ClienteServicio:
    """Cliente síncrono hacia otro servicio de la arquitectura.

    Es síncrono a propósito: lo usan los hilos del pool de procesamiento del
    Servicio de Solicitudes, donde cada hilo bloquea en su propia llamada.
    """

    def __init__(
        self,
        destino: str,
        *,
        timeout: float = TIMEOUT_INTERNO,
        reintentos: int = REINTENTOS_INTERNOS,
    ) -> None:
        self.destino = destino
        self.reintentos = reintentos
        self._cliente = httpx.Client(base_url=url_de(destino), timeout=timeout)

    def cerrar(self) -> None:
        self._cliente.close()

    def __enter__(self) -> ClienteServicio:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.cerrar()

    def pedir(
        self,
        metodo: str,
        ruta: str,
        *,
        json: Any | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        ultimo_error: Exception | None = None
        for intento in range(1, self.reintentos + 2):
            inicio = time.perf_counter()
            try:
                respuesta = self._cliente.request(
                    metodo, ruta, json=json, params=params, headers=headers
                )
                ms = (time.perf_counter() - inicio) * 1000
                log.debug(
                    "%s %s%s -> %s (%.1f ms, intento %d)",
                    metodo,
                    self.destino,
                    ruta,
                    respuesta.status_code,
                    ms,
                    intento,
                )
                if respuesta.status_code >= 500 and intento <= self.reintentos:
                    ultimo_error = httpx.HTTPStatusError(
                        f"HTTP {respuesta.status_code}",
                        request=respuesta.request,
                        response=respuesta,
                    )
                    time.sleep(0.15 * intento)
                    continue
                return respuesta
            except httpx.HTTPError as exc:
                ultimo_error = exc
                log.warning(
                    "Fallo de comunicación con '%s%s' (intento %d/%d): %s",
                    self.destino,
                    ruta,
                    intento,
                    self.reintentos + 1,
                    exc,
                )
                if intento <= self.reintentos:
                    time.sleep(0.15 * intento)

        raise ServicioNoDisponible(self.destino, str(ultimo_error))

    def get(self, ruta: str, **kwargs: Any) -> httpx.Response:
        return self.pedir("GET", ruta, **kwargs)

    def post(self, ruta: str, **kwargs: Any) -> httpx.Response:
        return self.pedir("POST", ruta, **kwargs)

    def put(self, ruta: str, **kwargs: Any) -> httpx.Response:
        return self.pedir("PUT", ruta, **kwargs)

    def patch(self, ruta: str, **kwargs: Any) -> httpx.Response:
        return self.pedir("PATCH", ruta, **kwargs)

    def delete(self, ruta: str, **kwargs: Any) -> httpx.Response:
        return self.pedir("DELETE", ruta, **kwargs)

    def json(self, metodo: str, ruta: str, **kwargs: Any) -> Any:
        """Ejecuta la petición y devuelve el cuerpo JSON, validando el estado."""
        respuesta = self.pedir(metodo, ruta, **kwargs)
        if respuesta.status_code >= 400:
            raise ServicioNoDisponible(
                self.destino, f"HTTP {respuesta.status_code}: {respuesta.text[:200]}"
            )
        return respuesta.json()
