"use client";

/**
 * Observer distribuido en funcionamiento.
 *
 * Muestra los observadores suscritos, la traza de entregas y permite simular
 * la caída del Servicio de Notificaciones para comprobar que el flujo
 * principal continúa (RNF07, sección 8.4.3 del diseño).
 */

import { useCallback, useState } from "react";
import { Encabezado } from "@/components/Encabezado";
import {
  Aviso,
  Boton,
  Cargador,
  Etiqueta,
  Metrica,
  Tabla,
  Tarjeta,
  Vacio,
  estadoTono,
  fecha,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useSondeo } from "@/lib/sondeo";
import { useSesion } from "@/components/Sesion";
import type { EntregaEvento, EstadoEventos, Notificacion } from "@/lib/tipos";

interface ResumenNotificaciones {
  total: number;
  disponible: boolean;
  por_tipo: Record<string, number>;
}

export default function Notificaciones() {
  const { autenticado } = useSesion();
  const [errorAccion, setErrorAccion] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);

  const consultar = useCallback(async () => {
    const [notificaciones, resumen, eventos, entregas] = await Promise.all([
      api.get<Notificacion[]>("/api/notificaciones?limite=25"),
      api.get<ResumenNotificaciones>("/api/notificaciones/resumen"),
      api.get<EstadoEventos>("/api/eventos/estado"),
      api.get<EntregaEvento[]>("/api/eventos/entregas?limite=20"),
    ]);
    return { notificaciones, resumen, eventos, entregas };
  }, []);

  const { datos, error: errorConsulta, recargar } = useSondeo(consultar, 4000);
  const notificaciones = datos?.notificaciones ?? null;
  const resumen = datos?.resumen ?? null;
  const eventos = datos?.eventos ?? null;
  const entregas = datos?.entregas ?? [];
  const error = errorAccion ?? errorConsulta;

  async function accion(fn: () => Promise<unknown>) {
    setOcupado(true);
    setErrorAccion(null);
    try {
      await fn();
      recargar();
    } catch (e) {
      setErrorAccion(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setOcupado(false);
    }
  }

  const disponible = resumen?.disponible ?? true;

  return (
    <>
      <Encabezado
        nodo="Nodo 3 · Observer distribuido"
        titulo="Eventos y notificaciones"
        descripcion="El Servicio de Resultados publica el evento y el de Notificaciones, suscrito como observador, lo recibe por HTTP. Ninguno conoce la lógica interna del otro."
      />

      {error && (
        <div className="mb-5">
          <Aviso>{error}</Aviso>
        </div>
      )}

      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metrica titulo="Notificaciones generadas" valor={resumen?.total ?? "—"} tono="evento" />
        <Metrica
          titulo="Eventos publicados"
          valor={eventos?.eventos_publicados ?? "—"}
          detalle={`${eventos?.eventos_en_cola ?? 0} en cola de despacho`}
        />
        <Metrica
          titulo="Eventos archivados"
          valor={eventos?.eventos_archivados ?? "—"}
          tono={eventos?.eventos_archivados ? "alerta" : "neutro"}
          detalle="Tras agotar los reintentos"
        />
        <Metrica
          titulo="Estado del observador"
          valor={disponible ? "disponible" : "caído"}
          tono={disponible ? "exito" : "error"}
          detalle={`${eventos?.hilos_despachadores ?? 0} hilos despachadores`}
        />
      </div>

      <Tarjeta
        className="mb-6"
        titulo="Prueba de tolerancia a fallos"
        descripcion="Con el observador caído, el registro de resultados debe seguir funcionando: el evento se archiva y se reintenta cuando el servicio vuelve."
      >
        <div className="flex flex-wrap items-center gap-2.5">
          <Boton
            variante={disponible ? "peligro" : "primario"}
            disabled={!autenticado || ocupado}
            onClick={() =>
              accion(() =>
                api.put("/api/simulacion/disponibilidad", { disponible: !disponible }),
              )
            }
          >
            {disponible ? "Simular caída del servicio" : "Restablecer el servicio"}
          </Boton>
          <Boton
            variante="secundario"
            disabled={!autenticado || ocupado || !eventos?.eventos_archivados}
            onClick={() => accion(() => api.post("/api/eventos/reintentar"))}
          >
            Reintentar eventos archivados ({eventos?.eventos_archivados ?? 0})
          </Boton>
          {!autenticado && (
            <span className="text-[11px] text-texto-tenue">
              Inicie sesión para ejecutar la simulación.
            </span>
          )}
        </div>
        {!disponible && (
          <div className="mt-3">
            <Aviso tono="alerta">
              Caída simulada activa. Cree una solicitud: se procesará y su resultado quedará
              registrado igualmente, mientras el evento se archiva para reintento.
            </Aviso>
          </div>
        )}
      </Tarjeta>

      <div className="mb-6 grid gap-4 lg:grid-cols-2">
        <Tarjeta
          titulo="Observadores suscritos"
          descripcion="Registro de suscripciones del sujeto observable."
        >
          {!eventos ? (
            <Cargador filas={2} />
          ) : eventos.observadores.length === 0 ? (
            <Vacio mensaje="Ningún servicio se ha suscrito todavía." />
          ) : (
            <ul className="space-y-2">
              {eventos.observadores.map((o) => (
                <li
                  key={o.id}
                  className="rounded-lg border border-borde-suave bg-superficie-2/50 px-3.5 py-3"
                >
                  <p className="flex items-center gap-2 text-[13px] font-medium">
                    <span
                      className={`h-1.5 w-1.5 rounded-full ${o.activa ? "latido bg-exito" : "bg-error"}`}
                    />
                    {o.servicio}
                  </p>
                  {/* La URL de callback no tiene puntos de corte naturales. */}
                  <p className="mt-1 break-all font-mono text-[11px] text-texto-suave">
                    {o.tipo_evento} → {o.callback_url}
                  </p>
                </li>
              ))}
            </ul>
          )}
        </Tarjeta>

        <Tarjeta
          titulo="Traza de entregas"
          descripcion="Cada intento del publicador hacia sus observadores, con el número de reintentos."
        >
          {entregas.length === 0 ? (
            <Vacio mensaje="Sin entregas registradas." />
          ) : (
            <Tabla columnas={["Estado", "Destino", "Intentos", "Momento"]}>
              {entregas.map((e, i) => (
                <tr key={`${e.evento_id}-${i}`} className="hover:bg-superficie-2/50">
                  <td className="px-3 py-2">
                    <Etiqueta tono={estadoTono(e.estado)}>{e.estado}</Etiqueta>
                  </td>
                  <td className="px-3 py-2 text-texto-suave">{e.destino}</td>
                  <td className="px-3 py-2 font-mono">{e.intentos}</td>
                  <td className="px-3 py-2 font-mono text-texto-tenue">{fecha(e.momento)}</td>
                </tr>
              ))}
            </Tabla>
          )}
        </Tarjeta>
      </div>

      <Tarjeta
        titulo="Notificaciones enviadas"
        descripcion="Generadas por el observador a partir de cada evento recibido. El envío real está simulado."
      >
        {!notificaciones ? (
          <Cargador filas={4} />
        ) : notificaciones.length === 0 ? (
          <Vacio mensaje="Aún no se han generado notificaciones." />
        ) : (
          <ul className="space-y-2">
            {notificaciones.map((n) => (
              <li
                key={n.id}
                className="rounded-lg border border-borde-suave bg-superficie-2/50 px-4 py-3"
              >
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="min-w-0 break-words text-[13px] font-medium">{n.asunto}</p>
                  <div className="flex items-center gap-2">
                    <Etiqueta tono="evento">{n.tipo_evento}</Etiqueta>
                    <span className="font-mono text-[11px] text-texto-tenue">
                      {fecha(n.recibido_en)}
                    </span>
                  </div>
                </div>
                <p className="mt-1.5 text-[11px] leading-relaxed text-texto-suave">{n.mensaje}</p>
                <p className="mt-1.5 break-words font-mono text-[11px] text-texto-tenue">
                  → {n.destinatario} · canal {n.canal} · intento {n.intento_entrega}
                </p>
              </li>
            ))}
          </ul>
        )}
      </Tarjeta>
    </>
  );
}
