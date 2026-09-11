"""Servicio de Solicitudes (Nodo 2 - Procesamiento, puerto 8001).

Es el componente central del prototipo: concentra el procesamiento concurrente
(pool de hilos configurable) y la coordinación entre servicios (Mediator).

Recorrido de una solicitud:

    POST /solicitudes
      → validación del cliente y la muestra (vía Mediator)
      → persistencia en estado 'en_cola'
      → envío al pool de hilos
      → un hilo libre la toma y ejecuta el análisis
      → el Mediator registra el resultado en el Servicio de Resultados
      → el Servicio de Resultados publica 'resultado.disponible'
      → el Servicio de Notificaciones recibe el evento
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from labcloud.services.solicitudes import bench
from labcloud.services.solicitudes.mediator import ErrorMediacion, MediadorAnalisis
from labcloud.services.solicitudes.models import EjecucionPrueba, Solicitud
from labcloud.services.solicitudes.pool import PoolProcesamiento
from labcloud.services.solicitudes.schemas import (
    ComparativaPeticion,
    ConfiguracionHilos,
    PruebaCargaPeticion,
    PruebaCargaSalida,
    SolicitudCrear,
    SolicitudSalida,
)
from labcloud.shared.config import DURACION_ANALISIS, HILOS_INICIALES
from labcloud.shared.db import Database
from labcloud.shared.service import crear_app

log = logging.getLogger("labcloud.solicitudes")
db = Database("solicitudes")

#: Conjunto controlado de hilos del nodo de procesamiento.
pool = PoolProcesamiento(HILOS_INICIALES)

#: Mediador que coordina Clientes, Muestras y Resultados.
mediador = MediadorAnalisis()

_contador = {"valor": 0}
_lock_codigo = threading.Lock()


def _siguiente_codigo() -> str:
    with _lock_codigo:
        _contador["valor"] += 1
        return f"SOL-{datetime.now(UTC):%Y%m%d}-{_contador['valor']:05d}"


def _inicializar() -> None:
    db.crear_tablas()
    with db.sesion() as session:
        total = session.scalar(select(func.count(Solicitud.id))) or 0
    _contador["valor"] = total
    log.info("Pool de procesamiento iniciado con %d hilos", pool.hilos)


def _detener() -> None:
    pool.apagar()
    mediador.cerrar()


app: FastAPI = crear_app("solicitudes", al_iniciar=_inicializar, al_detener=_detener)
Sesion = Annotated[Session, Depends(db.dependencia)]


# --- Trabajo que ejecuta cada hilo del pool ---------------------------------


def _trabajo_analisis(
    solicitud_id: str, contexto: dict[str, Any], duracion_s: float | None
) -> dict[str, Any]:
    """Función que corre dentro de un hilo del pool.

    Abre sus propias sesiones de base de datos porque se ejecuta fuera del
    ciclo de la petición HTTP y en un hilo distinto al que la recibió.
    """
    hilo = threading.current_thread().name
    espera_ms = pool.espera_en_cola_actual()
    inicio = time.perf_counter()

    with db.sesion() as session:
        solicitud = session.get(Solicitud, solicitud_id)
        if solicitud:
            solicitud.estado = "en_proceso"
            solicitud.hilo_procesamiento = hilo
            solicitud.espera_cola_ms = round(espera_ms, 2)
            solicitud.intentos += 1

    try:
        resultado = mediador.procesar(contexto, duracion_analisis_s=duracion_s)
    except Exception as exc:
        with db.sesion() as session:
            solicitud = session.get(Solicitud, solicitud_id)
            if solicitud:
                solicitud.estado = "fallida"
                solicitud.error = f"{type(exc).__name__}: {exc}"[:255]
                solicitud.duracion_ms = round((time.perf_counter() - inicio) * 1000, 2)
        raise

    duracion_ms = (time.perf_counter() - inicio) * 1000
    with db.sesion() as session:
        solicitud = session.get(Solicitud, solicitud_id)
        if solicitud:
            solicitud.estado = "resultado_disponible"
            solicitud.resultado_id = resultado["id"]
            solicitud.duracion_ms = round(duracion_ms, 2)
            solicitud.error = ""
    return resultado


def _contexto_de(solicitud: Solicitud) -> dict[str, Any]:
    return {
        "solicitud_id": solicitud.id,
        "codigo": solicitud.codigo,
        "cliente_id": solicitud.cliente_id,
        "cliente_nombre": solicitud.cliente_nombre,
        "cliente_email": solicitud.cliente_email,
        "muestra_id": solicitud.muestra_id,
        "codigo_muestra": solicitud.codigo_muestra,
        "tipo_analisis": solicitud.tipo_analisis,
        "observaciones": solicitud.observaciones,
    }


# --- Solicitudes de análisis ------------------------------------------------


@app.post("/solicitudes", response_model=SolicitudSalida, tags=["solicitudes"])
async def crear_solicitud(
    datos: SolicitudCrear, respuesta: Response, session: Sesion
) -> Solicitud:
    """Registra una solicitud y la envía al pool de procesamiento.

    Con ``esperar_resultado=true`` la respuesta llega cuando el análisis
    termina (201). Con ``false`` responde 202 de inmediato y el hilo continúa
    trabajando en segundo plano.
    """
    try:
        cliente = mediador.obtener_cliente(datos.cliente_id)
        muestra = mediador.obtener_muestra(datos.muestra_id)
    except ErrorMediacion as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    solicitud = Solicitud(
        codigo=_siguiente_codigo(),
        cliente_id=datos.cliente_id,
        cliente_nombre=cliente.get("nombre", ""),
        cliente_email=cliente.get("email", ""),
        muestra_id=datos.muestra_id,
        codigo_muestra=(muestra or {}).get("codigo", ""),
        tipo_analisis=datos.tipo_analisis,
        prioridad=datos.prioridad,
        observaciones=datos.observaciones,
        estado="en_cola",
    )
    session.add(solicitud)
    session.flush()
    # Se confirma antes de encolar: el hilo del pool usará su propia sesión.
    session.commit()

    contexto = _contexto_de(solicitud)
    futuro = pool.enviar(solicitud.codigo, _trabajo_analisis, solicitud.id, contexto, None)

    if not datos.esperar_resultado:
        respuesta.status_code = status.HTTP_202_ACCEPTED
        log.info("Solicitud %s aceptada; se procesará en segundo plano", solicitud.codigo)
        return solicitud

    try:
        await asyncio.wrap_future(futuro)
    except Exception as exc:
        log.error("Solicitud %s falló: %s", solicitud.codigo, exc)

    # El hilo del pool escribió desde otra sesión: se descarta la copia en caché.
    session.expire_all()
    respuesta.status_code = status.HTTP_201_CREATED
    return session.get(Solicitud, solicitud.id) or solicitud


@app.get("/solicitudes", response_model=list[SolicitudSalida], tags=["solicitudes"])
def listar_solicitudes(
    session: Sesion,
    estado: str | None = None,
    cliente_id: str | None = None,
    limite: Annotated[int, Query(ge=1, le=500)] = 50,
) -> list[Solicitud]:
    consulta = select(Solicitud).order_by(Solicitud.creada_en.desc())
    if estado:
        consulta = consulta.where(Solicitud.estado == estado)
    if cliente_id:
        consulta = consulta.where(Solicitud.cliente_id == cliente_id)
    return list(session.scalars(consulta.limit(limite)))


@app.get("/solicitudes/resumen", tags=["solicitudes"])
def resumen_solicitudes(session: Sesion) -> dict:
    total = session.scalar(select(func.count(Solicitud.id))) or 0
    por_estado = session.execute(
        select(Solicitud.estado, func.count(Solicitud.id)).group_by(Solicitud.estado)
    ).all()
    promedio = session.scalar(
        select(func.avg(Solicitud.duracion_ms)).where(Solicitud.duracion_ms > 0)
    )
    espera = session.scalar(
        select(func.avg(Solicitud.espera_cola_ms)).where(Solicitud.espera_cola_ms > 0)
    )
    por_hilo = session.execute(
        select(Solicitud.hilo_procesamiento, func.count(Solicitud.id))
        .where(Solicitud.hilo_procesamiento != "")
        .group_by(Solicitud.hilo_procesamiento)
    ).all()
    return {
        "total": total,
        "por_estado": {estado: cantidad for estado, cantidad in por_estado},
        "duracion_promedio_ms": round(float(promedio or 0), 2),
        "espera_promedio_ms": round(float(espera or 0), 2),
        "solicitudes_por_hilo": {hilo: cantidad for hilo, cantidad in por_hilo},
        "pool": pool.estado(),
    }


@app.get("/solicitudes/{solicitud_id}", response_model=SolicitudSalida, tags=["solicitudes"])
def obtener_solicitud(solicitud_id: str, session: Sesion) -> Solicitud:
    solicitud = session.get(Solicitud, solicitud_id)
    if not solicitud:
        solicitud = session.scalar(select(Solicitud).where(Solicitud.codigo == solicitud_id))
    if not solicitud:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Solicitud no encontrada")
    return solicitud


@app.post(
    "/solicitudes/{solicitud_id}/reprocesar",
    response_model=SolicitudSalida,
    tags=["solicitudes"],
)
async def reprocesar(solicitud_id: str, session: Sesion) -> Solicitud:
    """Reintenta una solicitud fallida, por ejemplo tras recuperar un servicio."""
    solicitud = session.get(Solicitud, solicitud_id)
    if not solicitud:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Solicitud no encontrada")

    contexto = _contexto_de(solicitud)
    solicitud.estado = "en_cola"
    session.commit()

    futuro = pool.enviar(
        f"{solicitud.codigo}-r{solicitud.intentos + 1}",
        _trabajo_analisis,
        solicitud.id,
        contexto,
        None,
    )
    codigo = solicitud.codigo
    try:
        await asyncio.wrap_future(futuro)
    except Exception as exc:
        log.error("Reproceso de %s falló: %s", codigo, exc)
    session.expire_all()
    return session.get(Solicitud, solicitud_id) or solicitud


# --- Configuración y estado de la concurrencia ------------------------------


@app.get("/concurrencia", tags=["concurrencia"])
def estado_concurrencia() -> dict:
    """Estado del pool de hilos y del mediador."""
    return {
        "pool": pool.estado(),
        "mediador": mediador.estado(),
        "duracion_analisis_s": DURACION_ANALISIS,
        "hilos_del_proceso": [h.name for h in threading.enumerate()],
    }


@app.put("/concurrencia", tags=["concurrencia"])
def configurar_hilos(configuracion: ConfiguracionHilos) -> dict:
    """Cambia la cantidad de hilos del pool sin reiniciar el servicio (RF09)."""
    cambio = pool.redimensionar(configuracion.hilos)
    return {**cambio, "estado": pool.estado()}


@app.get("/concurrencia/mediciones", tags=["concurrencia"])
def mediciones(limite: Annotated[int, Query(ge=1, le=500)] = 100) -> list[dict]:
    """Detalle por tarea: hilo, espera en cola, procesamiento y concurrencia."""
    return pool.mediciones(limite)


@app.post("/concurrencia/reiniciar-metricas", tags=["concurrencia"])
def reiniciar_metricas() -> dict:
    pool.reiniciar_metricas()
    return {"ok": True, "estado": pool.estado()}


# --- Pruebas de carga y escalabilidad ---------------------------------------


def _guardar_prueba(resumen: dict[str, Any]) -> EjecucionPrueba:
    registro = EjecucionPrueba(
        etiqueta=resumen["etiqueta"],
        solicitudes=resumen["solicitudes"],
        hilos=resumen["hilos"],
        duracion_analisis_s=resumen["duracion_analisis_s"],
        tiempo_total_s=resumen["tiempo_total_s"],
        throughput_rps=resumen["throughput_rps"],
        latencia_promedio_ms=resumen["latencia_promedio_ms"],
        latencia_p95_ms=resumen["latencia_p95_ms"],
        latencia_maxima_ms=resumen["latencia_maxima_ms"],
        espera_promedio_ms=resumen["espera_promedio_ms"],
        exitosas=resumen["exitosas"],
        fallidas=resumen["fallidas"],
        pico_concurrencia=resumen["pico_concurrencia"],
        hilos_utilizados=resumen["hilos_utilizados"],
        detalle=resumen["detalle"],
    )
    with db.sesion() as session:
        session.add(registro)
        session.flush()
        session.expunge(registro)
    return registro


def _contexto_prueba(peticion: PruebaCargaPeticion | ComparativaPeticion) -> dict[str, Any]:
    cliente_id = getattr(peticion, "cliente_id", "") or ""
    contexto: dict[str, Any] = {
        "tipo_analisis": getattr(peticion, "tipo_analisis", "hemograma"),
        "cliente_id": cliente_id,
        "cliente_nombre": "Prueba de carga",
        "cliente_email": "pruebas@labcloud.co",
        "muestra_id": "",
        "codigo_muestra": "",
        "observaciones": "Solicitud generada por la prueba de carga",
    }
    if cliente_id:
        try:
            cliente = mediador.obtener_cliente(cliente_id)
            contexto["cliente_nombre"] = cliente.get("nombre", "")
            contexto["cliente_email"] = cliente.get("email", "")
        except ErrorMediacion:
            log.warning("No se pudo resolver el cliente de la prueba; se usan datos ficticios")
    return contexto


@app.post("/pruebas/carga", tags=["pruebas"])
def prueba_de_carga(peticion: PruebaCargaPeticion) -> dict:
    """Lanza N solicitudes con una configuración de hilos y devuelve las métricas."""
    resumen = bench.ejecutar_prueba(
        pool,
        mediador,
        solicitudes=peticion.solicitudes,
        hilos=peticion.hilos,
        duracion_analisis_s=peticion.duracion_analisis_s,
        aislar_pool=peticion.aislar_pool,
        etiqueta=peticion.etiqueta,
        contexto=_contexto_prueba(peticion),
    )
    registro = _guardar_prueba(resumen)
    return {**resumen, "id": registro.id}


@app.post("/pruebas/comparativa", tags=["pruebas"])
def prueba_comparativa(peticion: ComparativaPeticion) -> dict:
    """Ejecuta la misma carga con 1, 2, 4 y 8 hilos (o la lista indicada)."""
    reporte = bench.ejecutar_comparativa(
        pool,
        mediador,
        solicitudes=peticion.solicitudes,
        configuraciones=peticion.configuraciones,
        duracion_analisis_s=peticion.duracion_analisis_s,
        aislar_pool=peticion.aislar_pool,
        contexto=_contexto_prueba(peticion),
    )
    for corrida in reporte["corridas"]:
        registro = _guardar_prueba(corrida)
        corrida["id"] = registro.id
    return reporte


@app.get("/pruebas", response_model=list[PruebaCargaSalida], tags=["pruebas"])
def listar_pruebas(
    session: Sesion, limite: Annotated[int, Query(ge=1, le=200)] = 50
) -> list[EjecucionPrueba]:
    return list(
        session.scalars(
            select(EjecucionPrueba).order_by(EjecucionPrueba.ejecutada_en.desc()).limit(limite)
        )
    )
