"""Infraestructura del patrón **Observer distribuido**.

El servicio que produce un cambio (el *sujeto*) publica un evento sin conocer
quién lo consumirá. Los servicios interesados (*observadores*) se registran
indicando una URL de callback y reciben el evento por HTTP.

Puntos clave del diseño (secciones 8.3.2 y 8.4.3 del documento):

* ``publicar()`` **no bloquea**: deja el evento en una cola y regresa de
  inmediato. El registro del resultado nunca espera a la notificación.
* La entrega ocurre en hilos despachadores en segundo plano, con reintentos y
  retroceso exponencial.
* Si un observador está caído, el evento termina en la cola de fallidos
  (*dead letter*) y puede reintentarse después, sin afectar el flujo principal.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from labcloud.shared.schemas import Evento, SolicitudSuscripcion, Suscripcion

log = logging.getLogger("labcloud.eventos")

MAX_INTENTOS = 4
ESPERA_BASE = 0.5


class EntregaEvento:
    """Traza de un intento de entrega, útil como evidencia de funcionamiento."""

    __slots__ = ("evento_id", "tipo", "destino", "estado", "intentos", "detalle", "momento")

    def __init__(
        self,
        evento_id: str,
        tipo: str,
        destino: str,
        estado: str,
        intentos: int,
        detalle: str = "",
    ) -> None:
        self.evento_id = evento_id
        self.tipo = tipo
        self.destino = destino
        self.estado = estado
        self.intentos = intentos
        self.detalle = detalle
        self.momento = datetime.now(UTC)

    def dict(self) -> dict[str, Any]:
        return {
            "evento_id": self.evento_id,
            "tipo": self.tipo,
            "destino": self.destino,
            "estado": self.estado,
            "intentos": self.intentos,
            "detalle": self.detalle,
            "momento": self.momento.isoformat(),
        }


class PublicadorEventos:
    """Sujeto observable distribuido.

    Mantiene el registro de observadores y entrega los eventos de forma
    asíncrona mediante un grupo de hilos despachadores.
    """

    def __init__(self, origen: str, *, despachadores: int = 2, timeout: float = 5.0) -> None:
        self.origen = origen
        self._timeout = timeout
        self._n_despachadores = despachadores
        self._suscripciones: dict[str, Suscripcion] = {}
        self._cola: deque[tuple[Evento, Suscripcion]] = deque()
        self._condicion = threading.Condition()
        self._lock = threading.RLock()
        self._hilos: list[threading.Thread] = []
        self._activo = False
        self._historial: deque[Evento] = deque(maxlen=500)
        self._entregas: deque[EntregaEvento] = deque(maxlen=500)
        self._fallidos: deque[tuple[Evento, Suscripcion]] = deque(maxlen=200)
        self.al_publicar: Callable[[Evento], None] | None = None

    # -- ciclo de vida -------------------------------------------------------

    def iniciar(self) -> None:
        if self._activo:
            return
        self._activo = True
        for i in range(self._n_despachadores):
            hilo = threading.Thread(
                target=self._bucle_despacho, name=f"evento-despachador-{i + 1}", daemon=True
            )
            hilo.start()
            self._hilos.append(hilo)
        log.info(
            "Publicador de eventos iniciado con %d hilos despachadores", self._n_despachadores
        )

    def detener(self) -> None:
        self._activo = False
        with self._condicion:
            self._condicion.notify_all()
        for hilo in self._hilos:
            hilo.join(timeout=2)
        self._hilos.clear()

    # -- registro de observadores -------------------------------------------

    def suscribir(self, peticion: SolicitudSuscripcion) -> Suscripcion:
        with self._lock:
            for existente in self._suscripciones.values():
                if (
                    existente.callback_url == peticion.callback_url
                    and existente.tipo_evento == peticion.tipo_evento
                ):
                    existente.activa = True
                    log.info(
                        "Suscripción reactivada: %s -> %s [%s]",
                        existente.servicio,
                        existente.callback_url,
                        existente.tipo_evento,
                    )
                    return existente
            suscripcion = Suscripcion(**peticion.model_dump())
            self._suscripciones[suscripcion.id] = suscripcion
            log.info(
                "Nuevo observador suscrito: %s -> %s [%s]",
                suscripcion.servicio,
                suscripcion.callback_url,
                suscripcion.tipo_evento,
            )
            return suscripcion

    def cancelar(self, suscripcion_id: str) -> bool:
        with self._lock:
            suscripcion = self._suscripciones.pop(suscripcion_id, None)
        if suscripcion:
            log.info("Observador dado de baja: %s", suscripcion.servicio)
        return suscripcion is not None

    def suscripciones(self, tipo_evento: str | None = None) -> list[Suscripcion]:
        with self._lock:
            items = list(self._suscripciones.values())
        if tipo_evento:
            items = [s for s in items if s.tipo_evento in (tipo_evento, "*")]
        return items

    # -- publicación ---------------------------------------------------------

    def publicar(self, tipo: str, datos: dict[str, Any]) -> Evento:
        """Encola el evento para todos los observadores y regresa de inmediato."""
        evento = Evento(tipo=tipo, origen=self.origen, datos=datos)
        destinatarios = [s for s in self.suscripciones(tipo) if s.activa]
        self._historial.appendleft(evento)
        if self.al_publicar:
            try:
                self.al_publicar(evento)
            except Exception:  # pragma: no cover - la persistencia no debe romper el flujo
                log.exception("No se pudo persistir el evento %s", evento.id)

        if not destinatarios:
            log.info("Evento '%s' publicado sin observadores suscritos", tipo)
            return evento

        with self._condicion:
            for suscripcion in destinatarios:
                self._cola.append((evento, suscripcion))
            self._condicion.notify_all()

        log.info(
            "Evento '%s' (%s) encolado para %d observador(es)",
            tipo,
            evento.id[:8],
            len(destinatarios),
        )
        return evento

    # -- despacho ------------------------------------------------------------

    def _bucle_despacho(self) -> None:
        while self._activo:
            with self._condicion:
                while self._activo and not self._cola:
                    self._condicion.wait(timeout=0.5)
                if not self._activo:
                    return
                evento, suscripcion = self._cola.popleft()
            self._entregar(evento, suscripcion)

    def _entregar(self, evento: Evento, suscripcion: Suscripcion) -> None:
        cuerpo = evento.model_dump(mode="json")
        for intento in range(1, MAX_INTENTOS + 1):
            cuerpo["intento"] = intento
            try:
                respuesta = httpx.post(
                    suscripcion.callback_url, json=cuerpo, timeout=self._timeout
                )
                if respuesta.status_code < 400:
                    self._entregas.appendleft(
                        EntregaEvento(
                            evento.id, evento.tipo, suscripcion.servicio, "entregado", intento
                        )
                    )
                    log.info(
                        "Evento '%s' (%s) entregado a %s en el intento %d",
                        evento.tipo,
                        evento.id[:8],
                        suscripcion.servicio,
                        intento,
                    )
                    return
                detalle = f"HTTP {respuesta.status_code}"
            except httpx.HTTPError as exc:
                detalle = type(exc).__name__

            log.warning(
                "Entrega fallida del evento '%s' a %s (intento %d/%d): %s",
                evento.tipo,
                suscripcion.servicio,
                intento,
                MAX_INTENTOS,
                detalle,
            )
            if intento < MAX_INTENTOS:
                time.sleep(ESPERA_BASE * (2 ** (intento - 1)))

        # El observador sigue caído: se archiva sin afectar el flujo principal.
        self._fallidos.appendleft((evento, suscripcion))
        self._entregas.appendleft(
            EntregaEvento(
                evento.id,
                evento.tipo,
                suscripcion.servicio,
                "fallido",
                MAX_INTENTOS,
                "observador no disponible; evento archivado para reintento manual",
            )
        )
        log.error(
            "Evento '%s' (%s) archivado tras %d intentos. El flujo principal no se interrumpe.",
            evento.tipo,
            evento.id[:8],
            MAX_INTENTOS,
        )

    def reintentar_fallidos(self) -> int:
        """Reencola los eventos archivados (usado tras recuperar un servicio)."""
        with self._condicion:
            pendientes = list(self._fallidos)
            self._fallidos.clear()
            for evento, suscripcion in pendientes:
                self._cola.append((evento, suscripcion))
            self._condicion.notify_all()
        if pendientes:
            log.info("Se reencolaron %d evento(s) archivados", len(pendientes))
        return len(pendientes)

    # -- consulta ------------------------------------------------------------

    def estado(self) -> dict[str, Any]:
        with self._condicion:
            pendientes = len(self._cola)
        return {
            "origen": self.origen,
            "activo": self._activo,
            "hilos_despachadores": self._n_despachadores,
            "eventos_en_cola": pendientes,
            "eventos_publicados": len(self._historial),
            "eventos_archivados": len(self._fallidos),
            "observadores": [s.model_dump(mode="json") for s in self.suscripciones()],
        }

    def historial(self, limite: int = 50) -> list[dict[str, Any]]:
        return [e.model_dump(mode="json") for e in list(self._historial)[:limite]]

    def entregas(self, limite: int = 50) -> list[dict[str, Any]]:
        return [e.dict() for e in list(self._entregas)[:limite]]


def registrar_observador(
    *,
    publicador_url: str,
    servicio: str,
    tipo_evento: str,
    callback_url: str,
    intentos: int = 10,
    espera: float = 1.0,
) -> bool:
    """Registra a este servicio como observador en el servicio publicador.

    Se reintenta porque el observador puede arrancar antes que el publicador.
    """
    cuerpo = {
        "servicio": servicio,
        "tipo_evento": tipo_evento,
        "callback_url": callback_url,
    }
    for intento in range(1, intentos + 1):
        try:
            respuesta = httpx.post(
                f"{publicador_url}/eventos/suscripciones", json=cuerpo, timeout=4.0
            )
            if respuesta.status_code < 400:
                log.info(
                    "Suscrito a '%s' en %s como observador de '%s'",
                    publicador_url,
                    servicio,
                    tipo_evento,
                )
                return True
        except httpx.HTTPError:
            pass
        log.debug("Publicador aún no disponible (intento %d/%d)", intento, intentos)
        time.sleep(espera)
    log.warning("No fue posible suscribirse a %s; se continuará sin eventos", publicador_url)
    return False
