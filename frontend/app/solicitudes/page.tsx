"use client";

/**
 * Servicio de Solicitudes (Nodo 2).
 *
 * Permite crear solicitudes de forma síncrona (se espera al resultado) o
 * asíncrona (se acepta y un hilo la procesa en segundo plano), y muestra qué
 * hilo atendió cada una.
 */

import { useCallback, useState } from "react";
import { Encabezado } from "@/components/Encabezado";
import {
  Aviso,
  Boton,
  Campo,
  Cargador,
  Etiqueta,
  Metrica,
  Tabla,
  Tarjeta,
  Vacio,
  claseEntrada,
  estadoTono,
  fecha,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useSondeo } from "@/lib/sondeo";
import { useSesion } from "@/components/Sesion";
import type { Cliente, Muestra, Solicitud } from "@/lib/tipos";

const ANALISIS = [
  "hemograma",
  "perfil_lipidico",
  "glucosa",
  "uroanalisis",
  "cultivo",
  "covid19",
  "general",
];
const PRIORIDADES = ["baja", "normal", "alta", "urgente"];

interface Resumen {
  total: number;
  por_estado: Record<string, number>;
  duracion_promedio_ms: number;
  espera_promedio_ms: number;
  solicitudes_por_hilo: Record<string, number>;
}

export default function Solicitudes() {
  const { autenticado } = useSesion();
  const [errorAccion, setErrorAccion] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [lote, setLote] = useState(5);
  const [formulario, setFormulario] = useState({
    cliente_id: "",
    muestra_id: "",
    tipo_analisis: "hemograma",
    prioridad: "normal",
    observaciones: "",
    esperar_resultado: true,
  });

  const consultar = useCallback(async () => {
    const [solicitudes, clientes, muestras, resumen] = await Promise.all([
      api.get<Solicitud[]>("/api/solicitudes?limite=40"),
      api.get<Cliente[]>("/api/clientes"),
      api.get<Muestra[]>("/api/muestras?limite=200"),
      api.get<Resumen>("/api/solicitudes/resumen"),
    ]);
    return { solicitudes, clientes, muestras, resumen };
  }, []);

  const { datos, error: errorConsulta, recargar } = useSondeo(consultar, 5000);
  const solicitudes = datos?.solicitudes ?? null;
  const clientes = datos?.clientes ?? [];
  const muestras = datos?.muestras ?? [];
  const resumen = datos?.resumen ?? null;
  const error = errorAccion ?? errorConsulta;

  // Mientras no se elija uno, se usa el primer cliente disponible.
  const clienteElegido = formulario.cliente_id || clientes[0]?.id || "";
  const peticion = { ...formulario, cliente_id: clienteElegido };

  async function ejecutar(accion: () => Promise<unknown>) {
    setEnviando(true);
    setErrorAccion(null);
    try {
      await accion();
      recargar();
    } catch (err) {
      setErrorAccion(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setEnviando(false);
    }
  }

  async function crear(e: React.FormEvent) {
    e.preventDefault();
    await ejecutar(() => api.post("/api/solicitudes", peticion));
  }

  /** Envía varias solicitudes a la vez para ver el reparto entre hilos. */
  async function enviarLote() {
    await ejecutar(() =>
      Promise.all(
        Array.from({ length: lote }, () =>
          api.post("/api/solicitudes", { ...peticion, esperar_resultado: false }),
        ),
      ),
    );
  }

  const muestrasCliente = muestras.filter(
    (m) => !clienteElegido || m.cliente_id === clienteElegido,
  );

  return (
    <>
      <Encabezado
        nodo="Nodo 2 · Servicio de Solicitudes"
        titulo="Solicitudes de análisis"
        descripcion="Cada solicitud entra por el Gateway, se encola y la toma un hilo del pool. El Mediator coordina la muestra, el resultado y el evento de notificación."
      />

      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metrica titulo="Solicitudes" valor={resumen?.total ?? "—"} />
        <Metrica
          titulo="Con resultado"
          valor={resumen?.por_estado?.resultado_disponible ?? 0}
          tono="exito"
        />
        <Metrica
          titulo="Duración media"
          valor={resumen?.duracion_promedio_ms?.toFixed(0) ?? "—"}
          unidad="ms"
          tono="acento"
        />
        <Metrica
          titulo="Espera media en cola"
          valor={resumen?.espera_promedio_ms?.toFixed(0) ?? "—"}
          unidad="ms"
          tono="alerta"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[330px_1fr]">
        <Tarjeta titulo="Nueva solicitud">
          <form onSubmit={crear} className="space-y-3.5">
            <Campo etiqueta="Cliente">
              <select
                value={clienteElegido}
                onChange={(e) =>
                  setFormulario({ ...formulario, cliente_id: e.target.value, muestra_id: "" })
                }
                className={claseEntrada}
                required
              >
                <option value="">Seleccione…</option>
                {clientes.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.nombre}
                  </option>
                ))}
              </select>
            </Campo>
            <Campo etiqueta="Muestra" ayuda="Opcional: la solicitud puede crearse sin muestra">
              <select
                value={formulario.muestra_id}
                onChange={(e) => setFormulario({ ...formulario, muestra_id: e.target.value })}
                className={claseEntrada}
              >
                <option value="">Sin muestra asociada</option>
                {muestrasCliente.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.codigo} · {m.tipo}
                  </option>
                ))}
              </select>
            </Campo>
            <Campo etiqueta="Tipo de análisis">
              <select
                value={formulario.tipo_analisis}
                onChange={(e) => setFormulario({ ...formulario, tipo_analisis: e.target.value })}
                className={claseEntrada}
              >
                {ANALISIS.map((a) => (
                  <option key={a} value={a}>
                    {a.replace("_", " ")}
                  </option>
                ))}
              </select>
            </Campo>
            <Campo etiqueta="Prioridad">
              <select
                value={formulario.prioridad}
                onChange={(e) => setFormulario({ ...formulario, prioridad: e.target.value })}
                className={claseEntrada}
              >
                {PRIORIDADES.map((p) => (
                  <option key={p} value={p}>
                    {p}
                  </option>
                ))}
              </select>
            </Campo>
            <Campo etiqueta="Observaciones">
              <input
                value={formulario.observaciones}
                onChange={(e) => setFormulario({ ...formulario, observaciones: e.target.value })}
                className={claseEntrada}
              />
            </Campo>

            <label className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-borde-suave bg-superficie-2/50 px-3 py-2.5">
              <input
                type="checkbox"
                checked={formulario.esperar_resultado}
                onChange={(e) =>
                  setFormulario({ ...formulario, esperar_resultado: e.target.checked })
                }
                className="mt-0.5 accent-[var(--color-acento)]"
              />
              <span className="text-[11px] leading-relaxed text-texto-suave">
                <b className="text-texto">Esperar el resultado.</b> Si se desmarca, el servicio
                responde 202 de inmediato y el hilo sigue trabajando en segundo plano.
              </span>
            </label>

            {error && <Aviso>{error}</Aviso>}
            {!autenticado && <Aviso tono="alerta">Inicie sesión para crear solicitudes.</Aviso>}
            <Boton tipo="submit" disabled={enviando || !autenticado} className="w-full">
              {enviando ? "Procesando…" : "Crear solicitud"}
            </Boton>

            <div className="border-t border-borde-suave pt-3.5">
              <Campo
                etiqueta="Envío simultáneo"
                ayuda="Dispara varias solicitudes a la vez para ver cómo se reparten entre los hilos"
              >
                <div className="flex gap-2">
                  <input
                    type="number"
                    min={2}
                    max={50}
                    value={lote}
                    onChange={(e) => setLote(Number(e.target.value))}
                    className={claseEntrada}
                  />
                  <Boton
                    variante="secundario"
                    onClick={enviarLote}
                    disabled={enviando || !autenticado}
                  >
                    Enviar
                  </Boton>
                </div>
              </Campo>
            </div>
          </form>
        </Tarjeta>

        <div className="min-w-0 space-y-4">
          {resumen && Object.keys(resumen.solicitudes_por_hilo).length > 0 && (
            <Tarjeta
              titulo="Reparto histórico entre hilos"
              descripcion="Cuántas solicitudes atendió cada hilo del pool."
            >
              <div className="flex flex-wrap gap-1.5">
                {Object.entries(resumen.solicitudes_por_hilo)
                  .sort(([a], [b]) => a.localeCompare(b))
                  .map(([hilo, n]) => (
                    <Etiqueta key={hilo} tono="hilo">
                      {hilo}: {n}
                    </Etiqueta>
                  ))}
              </div>
            </Tarjeta>
          )}

          <Tarjeta
            titulo="Solicitudes registradas"
            descripcion="El hilo y la espera en cola son la evidencia directa del procesamiento concurrente."
          >
            {!solicitudes ? (
              <Cargador filas={5} />
            ) : solicitudes.length === 0 ? (
              <Vacio mensaje="Aún no se han creado solicitudes." />
            ) : (
              <Tabla
                columnas={["Código", "Cliente", "Análisis", "Estado", "Hilo", "Espera", "Duración"]}
              >
                {solicitudes.map((s) => (
                  <tr key={s.id} className="hover:bg-superficie-2/50">
                    <td className="px-3 py-2 font-mono text-acento">{s.codigo}</td>
                    <td className="max-w-[150px] truncate px-3 py-2">{s.cliente_nombre}</td>
                    <td className="px-3 py-2 text-texto-suave">
                      {s.tipo_analisis.replace("_", " ")}
                    </td>
                    <td className="px-3 py-2">
                      <Etiqueta tono={estadoTono(s.estado)}>
                        {s.estado.replace(/_/g, " ")}
                      </Etiqueta>
                    </td>
                    <td className="px-3 py-2">
                      {s.hilo_procesamiento ? (
                        <span className="font-mono text-[11px] text-hilo">
                          {s.hilo_procesamiento}
                        </span>
                      ) : (
                        <span className="text-texto-tenue">—</span>
                      )}
                    </td>
                    <td className="px-3 py-2 font-mono text-texto-suave">
                      {s.espera_cola_ms ? `${s.espera_cola_ms} ms` : "—"}
                    </td>
                    <td className="px-3 py-2 font-mono">
                      {s.duracion_ms ? `${s.duracion_ms} ms` : "—"}
                    </td>
                  </tr>
                ))}
              </Tabla>
            )}
            {solicitudes?.some((s) => s.error) && (
              <div className="mt-3">
                <Aviso tono="alerta">
                  Hay solicitudes con error. Revise el estado de los servicios en el panel de nodos.
                </Aviso>
              </div>
            )}
            {solicitudes && solicitudes.length > 0 && (
              <p className="mt-3 text-[11px] text-texto-tenue">
                Última actualización: {fecha(solicitudes[0].actualizada_en)}
              </p>
            )}
          </Tarjeta>
        </div>
      </div>
    </>
  );
}
