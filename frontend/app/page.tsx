"use client";

/**
 * Panel de nodos: vista principal del sistema distribuido.
 *
 * Muestra la topología real (nodos, servicios, puertos y procesos), el estado
 * en vivo de cada nodo y el tráfico que el Gateway ha dirigido a cada servicio.
 */

import { useCallback } from "react";
import { Encabezado } from "@/components/Encabezado";
import { Aviso, Cargador, Etiqueta, Metrica, Tabla, Tarjeta } from "@/components/ui";
import { gateway } from "@/lib/api";
import { useSondeo } from "@/lib/sondeo";
import type { Arquitectura, SaludSistema } from "@/lib/tipos";

const COLOR_NODO: Record<string, string> = {
  "nodo-1": "text-acento",
  "nodo-2": "text-hilo",
  "nodo-3": "text-evento",
  "nodo-4": "text-alerta",
};

export default function PanelNodos() {
  const consultar = useCallback(async () => {
    const [arquitectura, salud] = await Promise.all([
      gateway.arquitectura() as Promise<Arquitectura>,
      gateway.salud() as Promise<SaludSistema>,
    ]);
    return { arquitectura, salud };
  }, []);

  const { datos, error } = useSondeo(consultar, 6000);
  const arquitectura = datos?.arquitectura ?? null;
  const salud = datos?.salud ?? null;

  const saludDe = (id: string) => salud?.servicios.find((s) => s.id === id);
  const trafico = salud?.trafico_por_servicio ?? {};
  const totalPeticiones = Object.values(trafico).reduce((a, b) => a + b.peticiones, 0);
  const totalHilos = (salud?.servicios ?? []).reduce(
    (a, s) => a + (s.hilos_activos ?? 0),
    0,
  );

  return (
    <>
      <Encabezado
        nodo="LabCloud S.A.S. · Arquitectura distribuida"
        titulo="Panel de nodos"
        descripcion="Cada servicio se ejecuta como un proceso independiente en su propio puerto, simulando los nodos de la infraestructura. Todo el tráfico del navegador entra por el API Gateway."
        accion={
          <div className="flex items-center gap-2 rounded-lg border border-borde bg-superficie px-3 py-2 text-xs">
            <span
              className={`latido h-1.5 w-1.5 rounded-full ${
                salud?.estado_general === "operativo" ? "bg-exito" : "bg-alerta"
              }`}
            />
            <span className="text-texto-suave">
              {salud ? `Sistema ${salud.estado_general}` : "Consultando…"}
            </span>
          </div>
        }
      />

      {error && (
        <div className="mb-6">
          <Aviso>{error}</Aviso>
        </div>
      )}

      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metrica
          titulo="Nodos lógicos"
          valor={arquitectura?.nodos.length ?? "—"}
          detalle="Agrupaciones de ejecución del sistema"
        />
        <Metrica
          titulo="Servicios activos"
          valor={salud ? `${salud.servicios_activos}/${salud.servicios_totales}` : "—"}
          tono={salud?.estado_general === "operativo" ? "exito" : "alerta"}
          detalle="Procesos respondiendo a /health"
        />
        <Metrica
          titulo="Hilos en ejecución"
          valor={totalHilos || "—"}
          tono="hilo"
          detalle="Suma de hilos vivos en todos los procesos"
        />
        <Metrica
          titulo="Peticiones dirigidas"
          valor={totalPeticiones}
          tono="acento"
          detalle="Reenvíos realizados por el Gateway"
        />
      </div>

      <Tarjeta
        className="mb-6"
        titulo="Flujo principal de una solicitud de análisis"
        descripcion="Combina comunicación síncrona (REST), procesamiento concurrente (hilos) y comunicación asíncrona (eventos)."
      >
        <div className="-mx-5 overflow-x-auto px-5">
          <div className="flex min-w-max items-center gap-2 font-mono text-[11px]">
            {[
              { t: "Usuario", c: "text-texto-suave" },
              { t: "API Gateway", c: "text-acento" },
              { t: "Servicio de Solicitudes", c: "text-hilo" },
              { t: "Hilo del pool", c: "text-hilo" },
              { t: "Servicio de Resultados", c: "text-evento" },
              { t: "evento", c: "text-evento" },
              { t: "Notificaciones", c: "text-evento" },
            ].map((paso, i, arr) => (
              <span key={paso.t} className="flex items-center gap-2">
                <span
                  className={`rounded-md border border-borde bg-superficie-2 px-2.5 py-1.5 ${paso.c}`}
                >
                  {paso.t}
                </span>
                {i < arr.length - 1 && <span className="text-texto-tenue">→</span>}
              </span>
            ))}
          </div>
        </div>
      </Tarjeta>

      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        {!arquitectura && <Cargador filas={4} />}
        {arquitectura?.nodos.map((nodo) => (
          <Tarjeta
            key={nodo.id}
            className="aparecer"
            titulo={
              <span className={COLOR_NODO[nodo.id] ?? ""}>{nodo.nombre}</span>
            }
            descripcion={nodo.responsabilidad}
          >
            <ul className="space-y-2.5">
              {nodo.servicios.map((servicio) => {
                const estado = saludDe(servicio.id);
                const activo = servicio.id === "gateway" ? true : estado?.alcanzable;
                const t = trafico[servicio.id];
                return (
                  <li
                    key={servicio.id}
                    className="rounded-lg border border-borde-suave bg-superficie-2/50 px-3.5 py-3"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="flex items-center gap-2 text-[13px] font-medium">
                          <span
                            className={`h-1.5 w-1.5 shrink-0 rounded-full ${
                              activo ? "latido bg-exito" : "bg-error"
                            }`}
                          />
                          {servicio.nombre}
                        </p>
                        <p className="mt-1 text-[11px] leading-relaxed text-texto-suave">
                          {servicio.descripcion}
                        </p>
                      </div>
                      <span className="shrink-0 font-mono text-[11px] text-texto-tenue">
                        :{servicio.puerto}
                      </span>
                    </div>

                    <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
                      {servicio.patrones.map((p) => (
                        <Etiqueta key={p} tono="acento">
                          {p}
                        </Etiqueta>
                      ))}
                      {estado?.pid && (
                        <Etiqueta>pid {estado.pid}</Etiqueta>
                      )}
                      {estado?.hilos_activos !== undefined && (
                        <Etiqueta tono="hilo">{estado.hilos_activos} hilos</Etiqueta>
                      )}
                      {t && (
                        <Etiqueta tono={t.errores ? "alerta" : "neutro"}>
                          {t.peticiones} peticiones · {t.latencia_promedio_ms} ms
                        </Etiqueta>
                      )}
                      {!activo && servicio.id !== "gateway" && (
                        <Etiqueta tono="error">sin respuesta</Etiqueta>
                      )}
                    </div>
                  </li>
                );
              })}
            </ul>
          </Tarjeta>
        ))}
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Tarjeta
          titulo="Patrones de diseño aplicados"
          descripcion="Cada patrón responde a una necesidad concreta de la arquitectura distribuida."
        >
          <ul className="space-y-3">
            {arquitectura?.patrones.map((p) => (
              <li key={p.nombre} className="border-l-2 border-acento/40 pl-3.5">
                <p className="text-[13px] font-medium">
                  {p.nombre}
                  <span className="ml-2 text-[11px] font-normal text-texto-tenue">
                    {p.componente}
                  </span>
                </p>
                <p className="mt-0.5 text-[11px] leading-relaxed text-texto-suave">
                  {p.aporte}
                </p>
              </li>
            )) ?? <Cargador filas={3} />}
          </ul>
        </Tarjeta>

        <Tarjeta
          titulo="Tabla de enrutamiento del Gateway"
          descripcion="Traducción de cada ruta pública hacia el servicio interno que la atiende."
        >
          <Tabla columnas={["Ruta pública", "Servicio", "Ruta interna", "Token"]}>
            {arquitectura?.rutas.map((r) => (
              <tr key={r.publica} className="hover:bg-superficie-2/50">
                <td className="px-3 py-2 font-mono text-acento">{r.publica}</td>
                <td className="px-3 py-2 text-texto-suave">{r.servicio}</td>
                <td className="px-3 py-2 font-mono text-texto-tenue">{r.interna}</td>
                <td className="px-3 py-2">
                  {r.requiere_token ? (
                    <Etiqueta tono="alerta">escritura</Etiqueta>
                  ) : (
                    <Etiqueta tono="exito">pública</Etiqueta>
                  )}
                </td>
              </tr>
            ))}
          </Tabla>
        </Tarjeta>
      </div>
    </>
  );
}
