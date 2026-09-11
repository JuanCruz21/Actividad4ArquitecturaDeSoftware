"""API Gateway (Nodo 1 - Entrada y acceso, puerto 8000).

Punto de entrada único del sistema. Aplica el patrón **Proxy**: el cliente
—el frontend Next.js— solo conoce este puerto, y el Gateway decide a qué
servicio interno corresponde cada petición, valida el acceso y devuelve la
respuesta.

Además expone los endpoints de arquitectura y salud que alimentan el panel de
control del frontend con el estado real de los nodos.
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from fastapi import FastAPI, HTTPException, Request, Response, status

from labcloud import __version__
from labcloud.gateway.proxy import (
    EstadisticasProxy,
    ProxyServicio,
    ServicioInalcanzable,
    filtrar_encabezados,
)
from labcloud.gateway.routing import RUTAS, resolver
from labcloud.shared.config import NODOS, ORDEN_ARRANQUE, SERVICIOS, url_de
from labcloud.shared.security import TokenInvalido, token_de_encabezado, validar_token
from labcloud.shared.service import crear_app

log = logging.getLogger("labcloud.gateway")

#: Política de acceso del Gateway:
#:   "escritura" (por defecto) exige token para POST/PUT/PATCH/DELETE
#:   "siempre"   exige token en toda petición
#:   "nunca"     desactiva la validación (solo para demostraciones)
MODO_AUTENTICACION = os.getenv("LABCLOUD_AUTH_MODO", "escritura").lower()
METODOS_ESCRITURA = {"POST", "PUT", "PATCH", "DELETE"}

estadisticas = EstadisticasProxy()

#: Un representante (Proxy) por cada servicio interno.
representantes: dict[str, ProxyServicio] = {
    service_id: ProxyServicio(service_id, estadisticas)
    for service_id in SERVICIOS
    if service_id != "gateway"
}


async def _cerrar() -> None:
    await asyncio.gather(*(p.cerrar() for p in representantes.values()))


def _al_iniciar() -> None:
    log.info("Política de autenticación: %s", MODO_AUTENTICACION)
    for ruta in RUTAS:
        log.info("  %-22s -> %-14s %s", ruta.prefijo_publico, ruta.servicio, ruta.prefijo_interno)


app: FastAPI = crear_app("gateway", al_iniciar=_al_iniciar, al_detener=_cerrar)


# --- Descripción de la arquitectura ----------------------------------------


@app.get("/arquitectura", tags=["arquitectura"])
def arquitectura() -> dict[str, Any]:
    """Topología del sistema: nodos, servicios, puertos y patrones aplicados."""
    return {
        "sistema": "LabCloud Distributed",
        "version": __version__,
        "nodos": [
            {
                "id": nodo.id,
                "nombre": nodo.nombre,
                "responsabilidad": nodo.responsabilidad,
                "servicios": [
                    {
                        "id": s.id,
                        "nombre": s.nombre,
                        "puerto": s.puerto,
                        "url": url_de(s.id),
                        "descripcion": s.descripcion,
                        "patrones": s.patrones,
                    }
                    for s in SERVICIOS.values()
                    if s.nodo == nodo.id
                ],
            }
            for nodo in NODOS.values()
        ],
        "rutas": [
            {
                "publica": r.prefijo_publico,
                "servicio": r.servicio,
                "interna": r.prefijo_interno,
                "requiere_token": not r.publico,
                "descripcion": r.descripcion,
            }
            for r in RUTAS
        ],
        "patrones": [
            {
                "nombre": "Proxy",
                "componente": "API Gateway",
                "aporte": "Control de acceso y direccionamiento; el cliente no conoce los "
                "servicios internos.",
            },
            {
                "nombre": "Mediator",
                "componente": "Servicio de Solicitudes",
                "aporte": "Coordina Clientes, Muestras y Resultados sin que se conozcan "
                "entre sí.",
            },
            {
                "nombre": "Observer distribuido",
                "componente": "Resultados → Notificaciones",
                "aporte": "El evento 'resultado.disponible' se publica sin acoplar al "
                "productor con el consumidor.",
            },
        ],
        "comunicacion": {
            "sincrona": "REST/HTTP entre el Gateway y los servicios internos",
            "asincrona": "Eventos HTTP del Servicio de Resultados hacia sus observadores",
            "concurrencia": "Pool de hilos configurable en el Servicio de Solicitudes",
        },
    }


@app.get("/salud", tags=["arquitectura"])
async def salud_del_sistema() -> dict[str, Any]:
    """Consulta en paralelo el estado de todos los nodos del sistema."""
    ids = [s for s in ORDEN_ARRANQUE if s != "gateway"]
    respuestas = await asyncio.gather(*(representantes[s].salud() for s in ids))

    servicios: list[dict[str, Any]] = []
    for service_id, salud in zip(ids, respuestas, strict=True):
        spec = SERVICIOS[service_id]
        servicios.append(
            {
                "id": service_id,
                "nombre": spec.nombre,
                "nodo": spec.nodo,
                "nodo_nombre": NODOS[spec.nodo].nombre,
                "puerto": spec.puerto,
                "url": url_de(service_id),
                "patrones": spec.patrones,
                **salud,
            }
        )

    activos = sum(1 for s in servicios if s.get("alcanzable"))
    return {
        "estado_general": "operativo" if activos == len(servicios) else "degradado",
        "servicios_activos": activos,
        "servicios_totales": len(servicios),
        "servicios": servicios,
        "trafico_por_servicio": estadisticas.resumen(),
    }


@app.get("/metricas", tags=["arquitectura"])
def metricas() -> dict[str, Any]:
    """Latencia y errores medidos por el Gateway para cada servicio."""
    return {"trafico_por_servicio": estadisticas.resumen()}


# --- Reenvío mediante el Proxy ----------------------------------------------


def _validar_acceso(request: Request, ruta_publica: bool) -> dict[str, Any] | None:
    """Aplica la política de autenticación antes de reenviar la petición."""
    if MODO_AUTENTICACION == "nunca" or ruta_publica:
        return None
    requiere = MODO_AUTENTICACION == "siempre" or request.method.upper() in METODOS_ESCRITURA

    token = token_de_encabezado(request.headers.get("authorization"))
    if not token:
        if requiere:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Se requiere un token de acceso para esta operación",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None

    try:
        return validar_token(token)
    except TokenInvalido as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, str(exc)) from exc


@app.api_route(
    "/api/{camino:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    tags=["proxy"],
    summary="Reenvío al servicio correspondiente",
)
async def reenviar(camino: str, request: Request) -> Response:
    """Resuelve el destino, valida el acceso y delega en el representante."""
    destino = resolver(f"/api/{camino}")
    if destino is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            f"No existe una ruta registrada para '/api/{camino}'",
        )
    ruta, ruta_interna = destino

    identidad = _validar_acceso(request, ruta.publico)

    encabezados = filtrar_encabezados(dict(request.headers))
    if identidad:
        # El Gateway propaga la identidad ya verificada a los servicios internos.
        encabezados["x-usuario-id"] = str(identidad.get("uid", ""))
        encabezados["x-usuario-rol"] = str(identidad.get("rol", ""))
    encabezados["x-reenviado-por"] = "labcloud-gateway"

    try:
        respuesta = await representantes[ruta.servicio].reenviar(
            request.method,
            ruta_interna,
            params=request.query_params,
            contenido=await request.body(),
            encabezados=encabezados,
        )
    except ServicioInalcanzable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            {
                "mensaje": f"El {SERVICIOS[exc.servicio].nombre} no está disponible",
                "servicio": exc.servicio,
                "detalle": exc.detalle,
                "sugerencia": "Verifique que el proceso del servicio esté en ejecución.",
            },
        ) from exc

    cabeceras = {
        k: v
        for k, v in respuesta.headers.items()
        if k.lower() not in {"content-length", "content-encoding", "transfer-encoding"}
    }
    cabeceras["x-servicio-origen"] = ruta.servicio
    cabeceras["x-nodo-origen"] = SERVICIOS[ruta.servicio].nodo
    return Response(
        content=respuesta.content,
        status_code=respuesta.status_code,
        headers=cabeceras,
        media_type=respuesta.headers.get("content-type"),
    )
