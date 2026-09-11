"""Patrón **Mediator** aplicado al procesamiento de una solicitud de análisis.

Problema que resuelve (sección 8.6.2 del diseño): en el flujo de una solicitud
intervienen los servicios de Clientes, Muestras y Resultados. Sin un mediador,
cada servicio tendría que conocer y llamar directamente a los demás, generando
una malla de dependencias difícil de mantener.

Con el Mediator, los servicios son *colegas* que no se conocen entre sí: el
mediador es el único componente que sabe a quién llamar y en qué orden. Agregar
un nuevo participante al flujo implica modificar solo esta clase.

    Clientes ─┐
    Muestras ─┼─► MediadorAnalisis ─► Resultados ─(evento)─► Notificaciones
    Solicitud ┘

Los métodos de esta clase se ejecutan dentro de los hilos del pool, por lo que
usan clientes HTTP síncronos (``httpx.Client`` es seguro entre hilos).
"""

from __future__ import annotations

import logging
import threading
from typing import Any

from labcloud.services.solicitudes.analisis import ejecutar_analisis
from labcloud.shared.http_client import ClienteServicio, ServicioNoDisponible

log = logging.getLogger("labcloud.mediator")


class ErrorMediacion(RuntimeError):
    """Falla irrecuperable durante la coordinación de un análisis."""


class MediadorAnalisis:
    """Coordina a los servicios que participan en una solicitud de análisis."""

    def __init__(self) -> None:
        # Colegas registrados. El resto del servicio nunca los usa directamente.
        self._colegas: dict[str, ClienteServicio] = {
            "clientes": ClienteServicio("clientes"),
            "muestras": ClienteServicio("muestras"),
            "resultados": ClienteServicio("resultados"),
        }
        self._llamadas: dict[str, int] = {nombre: 0 for nombre in self._colegas}
        self._lock = threading.Lock()

    def _colega(self, nombre: str) -> ClienteServicio:
        with self._lock:
            self._llamadas[nombre] += 1
        return self._colegas[nombre]

    def cerrar(self) -> None:
        for cliente in self._colegas.values():
            cliente.cerrar()

    # -- validaciones previas (se ejecutan antes de encolar) -----------------

    def obtener_cliente(self, cliente_id: str) -> dict[str, Any]:
        """Valida que el cliente exista consultando al Servicio de Clientes."""
        try:
            return self._colega("clientes").json("GET", f"/clientes/{cliente_id}")
        except ServicioNoDisponible as exc:
            raise ErrorMediacion(f"No fue posible validar el cliente: {exc.detalle}") from exc

    def obtener_muestra(self, muestra_id: str) -> dict[str, Any] | None:
        if not muestra_id:
            return None
        try:
            return self._colega("muestras").json("GET", f"/muestras/{muestra_id}")
        except ServicioNoDisponible as exc:
            raise ErrorMediacion(f"No fue posible validar la muestra: {exc.detalle}") from exc

    def crear_muestra(self, datos: dict[str, Any]) -> dict[str, Any]:
        return self._colega("muestras").json("POST", "/muestras", json=datos)

    # -- coordinación del análisis (se ejecuta dentro de un hilo del pool) ---

    def _marcar_muestra(self, muestra_id: str, estado: str) -> None:
        """Actualiza el estado de la muestra. No es crítico para el flujo."""
        if not muestra_id:
            return
        try:
            self._colega("muestras").patch(
                f"/muestras/{muestra_id}/estado", json={"estado": estado}
            )
        except ServicioNoDisponible as exc:
            log.warning("No se pudo marcar la muestra %s como '%s': %s", muestra_id, estado, exc)

    def procesar(
        self, contexto: dict[str, Any], *, duracion_analisis_s: float | None = None
    ) -> dict[str, Any]:
        """Ejecuta el análisis y registra el resultado coordinando a los colegas.

        Pasos:
          1. Marca la muestra como ``en_analisis`` (Servicio de Muestras).
          2. Procesa el análisis dentro del hilo actual.
          3. Registra el resultado (Servicio de Resultados), que a su vez
             publica el evento ``resultado.disponible``.
          4. Marca la muestra como ``procesada``.
        """
        hilo = threading.current_thread().name
        muestra_id = contexto.get("muestra_id", "")

        self._marcar_muestra(muestra_id, "en_analisis")

        valores, diagnostico, duracion_ms = ejecutar_analisis(
            contexto["tipo_analisis"], duracion_s=duracion_analisis_s
        )

        cuerpo = {
            "solicitud_id": contexto["solicitud_id"],
            "codigo_solicitud": contexto.get("codigo", ""),
            "cliente_id": contexto.get("cliente_id", ""),
            "cliente_nombre": contexto.get("cliente_nombre", ""),
            "cliente_email": contexto.get("cliente_email", ""),
            "muestra_id": muestra_id,
            "codigo_muestra": contexto.get("codigo_muestra", ""),
            "tipo_analisis": contexto["tipo_analisis"],
            "valores": valores,
            "diagnostico": diagnostico,
            "observaciones": contexto.get("observaciones", ""),
            "hilo_origen": hilo,
            "duracion_ms": round(duracion_ms, 2),
        }

        try:
            resultado = self._colega("resultados").json("POST", "/resultados", json=cuerpo)
        except ServicioNoDisponible as exc:
            raise ErrorMediacion(f"No fue posible registrar el resultado: {exc.detalle}") from exc

        self._marcar_muestra(muestra_id, "procesada")
        log.info(
            "Análisis '%s' coordinado por %s: resultado %s",
            contexto["tipo_analisis"],
            hilo,
            resultado["id"][:8],
        )
        return resultado

    # -- observabilidad ------------------------------------------------------

    def estado(self) -> dict[str, Any]:
        with self._lock:
            llamadas = dict(self._llamadas)
        return {
            "colegas": list(self._colegas),
            "llamadas_por_colega": llamadas,
            "total_llamadas": sum(llamadas.values()),
        }
