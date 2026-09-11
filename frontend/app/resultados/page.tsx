"use client";

/** Servicio de Resultados (Nodo 3). Sujeto del Observer distribuido. */

import { useCallback, useState } from "react";
import { Encabezado } from "@/components/Encabezado";
import {
  Aviso,
  Cargador,
  Etiqueta,
  Metrica,
  Tarjeta,
  Vacio,
  fecha,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useSondeo } from "@/lib/sondeo";
import type { Resultado } from "@/lib/tipos";

interface ResumenResultados {
  total: number;
  duracion_promedio_ms: number;
  por_tipo_analisis: Record<string, number>;
  eventos: { eventos_publicados: number; eventos_archivados: number; eventos_en_cola: number };
}

export default function Resultados() {
  const [abierto, setAbierto] = useState<string | null>(null);

  const consultar = useCallback(async () => {
    const [resultados, resumen] = await Promise.all([
      api.get<Resultado[]>("/api/resultados?limite=40"),
      api.get<ResumenResultados>("/api/resultados/resumen"),
    ]);
    return { resultados, resumen };
  }, []);

  const { datos, error } = useSondeo(consultar, 6000);
  const resultados = datos?.resultados ?? null;
  const resumen = datos?.resumen ?? null;

  return (
    <>
      <Encabezado
        nodo="Nodo 3 · Servicio de Resultados"
        titulo="Resultados de análisis"
        descripcion="Al registrar un resultado, el servicio publica el evento 'resultado.disponible' y responde de inmediato, sin esperar a que la notificación se entregue."
      />

      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metrica titulo="Resultados" valor={resumen?.total ?? "—"} />
        <Metrica
          titulo="Duración media del análisis"
          valor={resumen?.duracion_promedio_ms?.toFixed(0) ?? "—"}
          unidad="ms"
          tono="acento"
        />
        <Metrica
          titulo="Eventos publicados"
          valor={resumen?.eventos.eventos_publicados ?? "—"}
          tono="evento"
        />
        <Metrica
          titulo="Eventos archivados"
          valor={resumen?.eventos.eventos_archivados ?? "—"}
          tono={resumen?.eventos.eventos_archivados ? "alerta" : "neutro"}
          detalle="Pendientes de reintento"
        />
      </div>

      {error && (
        <div className="mb-5">
          <Aviso>{error}</Aviso>
        </div>
      )}

      <Tarjeta
        titulo="Informes registrados"
        descripcion="Cada informe conserva el hilo que lo produjo, lo que permite rastrear una solicitud desde su origen hasta el resultado."
      >
        {!resultados ? (
          <Cargador filas={4} />
        ) : resultados.length === 0 ? (
          <Vacio mensaje="Todavía no hay resultados registrados." />
        ) : (
          <ul className="space-y-2">
            {resultados.map((r) => (
              <li
                key={r.id}
                className="overflow-hidden rounded-lg border border-borde-suave bg-superficie-2/50"
              >
                <button
                  onClick={() => setAbierto(abierto === r.id ? null : r.id)}
                  className="flex w-full flex-wrap items-center justify-between gap-3 px-4 py-3 text-left transition hover:bg-superficie-2"
                >
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-2 text-[13px]">
                      <span className="font-mono text-acento">
                        {r.codigo_solicitud || r.solicitud_id.slice(0, 10)}
                      </span>
                      <span className="text-texto-suave">
                        {r.tipo_analisis.replace("_", " ")}
                      </span>
                    </p>
                    <p className="mt-0.5 truncate text-[11px] text-texto-suave">
                      {r.cliente_nombre || "—"} · {r.diagnostico}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {r.hilo_origen && <Etiqueta tono="hilo">{r.hilo_origen}</Etiqueta>}
                    <span className="font-mono text-[11px] text-texto-tenue">
                      {fecha(r.registrado_en)}
                    </span>
                    <span className="text-texto-tenue">{abierto === r.id ? "−" : "+"}</span>
                  </div>
                </button>

                {abierto === r.id && (
                  <div className="aparecer border-t border-borde-suave px-4 py-3">
                    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                      {Object.entries(r.valores).map(([nombre, v]) => (
                        <div
                          key={nombre}
                          className="rounded-md border border-borde-suave bg-fondo/50 px-3 py-2"
                        >
                          <p className="text-[11px] text-texto-tenue">
                            {nombre.replace(/_/g, " ")}
                          </p>
                          <p className="font-mono text-sm">
                            {v.valor}
                            <span className="ml-1 text-[11px] text-texto-suave">{v.unidad}</span>
                          </p>
                          <p className="text-[10px] text-texto-tenue">Rango: {v.rango}</p>
                        </div>
                      ))}
                    </div>
                    <p className="mt-3 break-words text-[11px] text-texto-suave">
                      Muestra: <span className="font-mono">{r.codigo_muestra || "sin muestra"}</span>{" "}
                      · Procesamiento:{" "}
                      <span className="font-mono">{r.duracion_ms.toFixed(1)} ms</span> ·
                      Destinatario: <span className="font-mono">{r.cliente_email || "—"}</span>
                    </p>
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
      </Tarjeta>
    </>
  );
}
