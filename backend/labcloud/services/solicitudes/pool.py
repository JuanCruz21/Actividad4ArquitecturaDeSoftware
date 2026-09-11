"""Pool de hilos configurable del Servicio de Solicitudes.

Implementa el mecanismo descrito en la sección 8.5 del diseño:

    Solicitudes recibidas → Cola de procesamiento → Hilos disponibles →
    Procesamiento → Respuesta

Si llegan cinco solicitudes y hay tres hilos configurados, tres comienzan a
procesarse de inmediato y las dos restantes esperan en la cola hasta que un
hilo quede libre. La cantidad de hilos se puede cambiar en caliente para
comparar configuraciones de 1, 2, 4 u 8 hilos durante las pruebas (RF09).

Además de ejecutar el trabajo, el pool mide para cada tarea el tiempo de
espera en cola y el tiempo de procesamiento, que son los insumos del análisis
de rendimiento y de detección de cuellos de botella (RNF05).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, TypeVar

log = logging.getLogger("labcloud.pool")

T = TypeVar("T")


@dataclass
class MedicionTarea:
    """Métricas de una tarea atendida por el pool."""

    referencia: str
    hilo: str
    espera_ms: float
    procesamiento_ms: float
    total_ms: float
    concurrencia_observada: int
    hilos_configurados: int
    exito: bool = True
    detalle: str = ""
    momento: float = field(default_factory=time.time)

    def dict(self) -> dict[str, Any]:
        return {
            "referencia": self.referencia,
            "hilo": self.hilo,
            "espera_ms": round(self.espera_ms, 2),
            "procesamiento_ms": round(self.procesamiento_ms, 2),
            "total_ms": round(self.total_ms, 2),
            "concurrencia_observada": self.concurrencia_observada,
            "hilos_configurados": self.hilos_configurados,
            "exito": self.exito,
            "detalle": self.detalle,
        }


class PoolProcesamiento:
    """Conjunto controlado de hilos con métricas y redimensionamiento en caliente."""

    def __init__(self, hilos: int, *, nombre: str = "solicitud-worker") -> None:
        self._nombre = nombre
        self._hilos = max(1, hilos)
        self._lock = threading.Lock()
        self._executor = self._nuevo_executor(self._hilos)
        self._en_cola = 0
        self._en_proceso = 0
        self._pico_concurrencia = 0
        self._total_procesadas = 0
        self._total_fallidas = 0
        self._mediciones: deque[MedicionTarea] = deque(maxlen=1000)
        # Contexto por hilo: permite a la tarea consultar cuánto esperó en cola.
        self._contexto = threading.local()

    # -- configuración -------------------------------------------------------

    def _nuevo_executor(self, hilos: int) -> ThreadPoolExecutor:
        return ThreadPoolExecutor(max_workers=hilos, thread_name_prefix=self._nombre)

    @property
    def hilos(self) -> int:
        return self._hilos

    def redimensionar(self, hilos: int) -> dict[str, Any]:
        """Cambia la cantidad de hilos disponibles sin detener el servicio.

        El pool anterior se cierra en segundo plano esperando a que sus tareas
        en curso terminen, de modo que ninguna solicitud se pierde.
        """
        hilos = max(1, min(64, int(hilos)))
        with self._lock:
            if hilos == self._hilos:
                return {"hilos": self._hilos, "cambio": False}
            anterior, viejo = self._hilos, self._executor
            self._hilos = hilos
            self._executor = self._nuevo_executor(hilos)
            self._pico_concurrencia = 0

        threading.Thread(
            target=lambda: viejo.shutdown(wait=True),
            name="pool-drenaje",
            daemon=True,
        ).start()
        log.info("Pool redimensionado: %d -> %d hilos", anterior, hilos)
        return {"hilos": hilos, "anterior": anterior, "cambio": True}

    # -- ejecución -----------------------------------------------------------

    def enviar(self, referencia: str, funcion: Callable[..., T], *args: Any) -> Future[T]:
        """Encola una tarea; devuelve el futuro con su resultado."""
        encolada_en = time.perf_counter()
        with self._lock:
            self._en_cola += 1
            executor = self._executor
            hilos_config = self._hilos
        log.debug("Solicitud %s encolada (%d en cola)", referencia, self._en_cola)
        return executor.submit(
            self._ejecutar, referencia, funcion, args, encolada_en, hilos_config
        )

    def _ejecutar(
        self,
        referencia: str,
        funcion: Callable[..., T],
        args: tuple[Any, ...],
        encolada_en: float,
        hilos_config: int,
    ) -> T:
        inicio = time.perf_counter()
        espera_ms = (inicio - encolada_en) * 1000
        hilo = threading.current_thread().name

        with self._lock:
            self._en_cola -= 1
            self._en_proceso += 1
            concurrencia = self._en_proceso
            self._pico_concurrencia = max(self._pico_concurrencia, concurrencia)

        self._contexto.referencia = referencia
        self._contexto.espera_ms = espera_ms

        log.info(
            "▶ %s tomada por %s (espera en cola: %.1f ms, %d hilo(s) trabajando)",
            referencia,
            hilo,
            espera_ms,
            concurrencia,
        )

        exito, detalle = True, ""
        try:
            return funcion(*args)
        except Exception as exc:
            exito = False
            detalle = f"{type(exc).__name__}: {exc}"
            log.exception("Error procesando %s en %s", referencia, hilo)
            raise
        finally:
            fin = time.perf_counter()
            procesamiento_ms = (fin - inicio) * 1000
            with self._lock:
                self._en_proceso -= 1
                self._total_procesadas += 1
                if not exito:
                    self._total_fallidas += 1
                self._mediciones.appendleft(
                    MedicionTarea(
                        referencia=referencia,
                        hilo=hilo,
                        espera_ms=espera_ms,
                        procesamiento_ms=procesamiento_ms,
                        total_ms=espera_ms + procesamiento_ms,
                        concurrencia_observada=concurrencia,
                        hilos_configurados=hilos_config,
                        exito=exito,
                        detalle=detalle,
                    )
                )
            log.info(
                "■ %s finalizada por %s en %.1f ms%s",
                referencia,
                hilo,
                procesamiento_ms,
                "" if exito else " (con error)",
            )

    def espera_en_cola_actual(self) -> float:
        """Milisegundos que la tarea en curso esperó antes de tomar un hilo."""
        return float(getattr(self._contexto, "espera_ms", 0.0))

    # -- consulta ------------------------------------------------------------

    def estado(self) -> dict[str, Any]:
        with self._lock:
            return {
                "hilos_configurados": self._hilos,
                "solicitudes_en_cola": self._en_cola,
                "solicitudes_en_proceso": self._en_proceso,
                "pico_concurrencia": self._pico_concurrencia,
                "total_procesadas": self._total_procesadas,
                "total_fallidas": self._total_fallidas,
                "hilos_vivos": [
                    h.name for h in threading.enumerate() if h.name.startswith(self._nombre)
                ],
            }

    def mediciones(self, limite: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return [m.dict() for m in list(self._mediciones)[:limite]]

    def reiniciar_metricas(self) -> None:
        with self._lock:
            self._mediciones.clear()
            self._pico_concurrencia = 0
            self._total_procesadas = 0
            self._total_fallidas = 0

    def apagar(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
