"use client";

/**
 * Laboratorio de hilos: configuración del pool y pruebas de carga.
 *
 * Cubre los requisitos RF09 y RF10 y el capítulo 10 del diseño: permite variar
 * la cantidad de hilos, lanzar N solicitudes, comparar configuraciones y
 * observar qué hilo atendió cada tarea y cuánto esperó en cola.
 */

import { useCallback, useState } from "react";
import { Encabezado } from "@/components/Encabezado";
import { GraficaComparativa } from "@/components/GraficaComparativa";
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
} from "@/components/ui";
import { api } from "@/lib/api";
import { useSondeo } from "@/lib/sondeo";
import { useSesion } from "@/components/Sesion";
import type {
  Comparativa,
  CorridaPrueba,
  EstadoConcurrencia,
  Medicion,
} from "@/lib/tipos";

// Serie por defecto: duplica los hilos hasta 64 para que la curva alcance el
// punto en que agregar concurrencia deja de aportar.
const CONFIGURACIONES = "1,2,4,8,16,32,64";

export default function LaboratorioHilos() {
  const { autenticado } = useSesion();
  const [comparativa, setComparativa] = useState<Comparativa | null>(null);
  const [ultima, setUltima] = useState<CorridaPrueba | null>(null);
  const [errorAccion, setErrorAccion] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState<string | null>(null);

  // `hilos` guarda lo que el usuario escribe; mientras no toque el campo se
  // muestra el tamaño real del pool que reporta el servicio.
  const [hilosEditados, setHilosEditados] = useState<number | null>(null);
  const [solicitudes, setSolicitudes] = useState(64);
  const [duracion, setDuracion] = useState(0.2);
  const [aislar, setAislar] = useState(true);
  const [configuraciones, setConfiguraciones] = useState(CONFIGURACIONES);

  const consultar = useCallback(async () => {
    const [estado, mediciones, historial] = await Promise.all([
      api.get<EstadoConcurrencia>("/api/concurrencia"),
      api.get<Medicion[]>("/api/concurrencia/mediciones?limite=40"),
      api.get<CorridaPrueba[]>("/api/pruebas?limite=12"),
    ]);
    return { estado, mediciones, historial };
  }, []);

  const { datos, error: errorConsulta, recargar } = useSondeo(consultar, 5000);
  const estado = datos?.estado ?? null;
  const mediciones = datos?.mediciones ?? [];
  const historial = datos?.historial ?? [];
  const error = errorAccion ?? errorConsulta;
  const hilos = hilosEditados ?? estado?.pool.hilos_configurados ?? 4;
  const setHilos = (valor: number) => setHilosEditados(valor);

  async function accion(nombre: string, fn: () => Promise<void>) {
    setOcupado(nombre);
    setErrorAccion(null);
    try {
      await fn();
    } catch (e) {
      setErrorAccion(e instanceof Error ? e.message : "Error desconocido");
    } finally {
      setOcupado(null);
      recargar();
    }
  }

  const aplicarHilos = () =>
    accion("hilos", async () => {
      await api.put("/api/concurrencia", { hilos });
    });

  const lanzarPrueba = () =>
    accion("carga", async () => {
      const r = await api.post<CorridaPrueba>("/api/pruebas/carga", {
        solicitudes,
        hilos,
        duracion_analisis_s: duracion,
        aislar_pool: aislar,
        etiqueta: `${solicitudes} solicitudes / ${hilos} hilos`,
      });
      setUltima(r);
      setComparativa(null);
    });

  const lanzarComparativa = () =>
    accion("comparativa", async () => {
      const lista = configuraciones
        .split(",")
        .map((x) => Number(x.trim()))
        .filter((x) => Number.isInteger(x) && x > 0 && x <= 64);
      if (!lista.length) throw new Error("Indique al menos una cantidad de hilos válida");
      const r = await api.post<Comparativa>("/api/pruebas/comparativa", {
        solicitudes,
        configuraciones: lista,
        duracion_analisis_s: duracion,
        aislar_pool: aislar,
      });
      setComparativa(r);
      setUltima(null);
    });

  const pool = estado?.pool;

  return (
    <>
      <Encabezado
        nodo="Nodo 2 · Servicio de Solicitudes"
        titulo="Laboratorio de hilos"
        descripcion="El servicio atiende las solicitudes con un conjunto controlado de hilos. Si llegan más solicitudes que hilos disponibles, las restantes esperan en cola hasta que un hilo se libere."
      />

      {!autenticado && (
        <div className="mb-5">
          <Aviso tono="alerta">
            Las pruebas modifican el estado del sistema: el Gateway exige un token para las
            operaciones de escritura. Inicie sesión para ejecutarlas.
          </Aviso>
        </div>
      )}
      {error && (
        <div className="mb-5">
          <Aviso>{error}</Aviso>
        </div>
      )}

      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metrica
          titulo="Hilos configurados"
          valor={pool?.hilos_configurados ?? "—"}
          tono="hilo"
          detalle="Tamaño actual del pool"
        />
        <Metrica
          titulo="En proceso"
          valor={pool?.solicitudes_en_proceso ?? "—"}
          tono="acento"
          detalle={`Pico observado: ${pool?.pico_concurrencia ?? 0}`}
        />
        <Metrica
          titulo="En cola"
          valor={pool?.solicitudes_en_cola ?? "—"}
          tono={pool?.solicitudes_en_cola ? "alerta" : "neutro"}
          detalle="Esperando un hilo libre"
        />
        <Metrica
          titulo="Total procesadas"
          valor={pool?.total_procesadas ?? "—"}
          detalle={`${pool?.total_fallidas ?? 0} con error`}
        />
      </div>

      <div className="mb-6 grid gap-4 lg:grid-cols-[320px_1fr]">
        <Tarjeta
          titulo="Configuración de la prueba"
          descripcion="Los hilos se ajustan en caliente, sin reiniciar el servicio."
        >
          <div className="space-y-4">
            <Campo etiqueta="Hilos del pool" ayuda="Entre 1 y 64">
              <div className="flex gap-2">
                <input
                  type="number"
                  min={1}
                  max={64}
                  value={hilos}
                  onChange={(e) => setHilos(Number(e.target.value))}
                  className={claseEntrada}
                />
                <Boton
                  variante="secundario"
                  onClick={aplicarHilos}
                  disabled={!autenticado || ocupado !== null}
                >
                  Aplicar
                </Boton>
              </div>
            </Campo>

            <Campo etiqueta="Solicitudes a generar">
              <input
                type="number"
                min={1}
                max={500}
                value={solicitudes}
                onChange={(e) => setSolicitudes(Number(e.target.value))}
                className={claseEntrada}
              />
            </Campo>

            <Campo
              etiqueta="Duración del análisis (s)"
              ayuda="Tiempo simulado de procesamiento por muestra"
            >
              <input
                type="number"
                min={0}
                max={5}
                step={0.05}
                value={duracion}
                onChange={(e) => setDuracion(Number(e.target.value))}
                className={claseEntrada}
              />
            </Campo>

            <label className="flex cursor-pointer items-start gap-2.5 rounded-lg border border-borde-suave bg-superficie-2/50 px-3 py-2.5">
              <input
                type="checkbox"
                checked={aislar}
                onChange={(e) => setAislar(e.target.checked)}
                className="mt-0.5 accent-[var(--color-acento)]"
              />
              <span className="text-[11px] leading-relaxed text-texto-suave">
                <b className="text-texto">Aislar el pool.</b> Ejecuta solo el análisis, sin
                llamar a los demás servicios. Mide la concurrencia sin el costo de la red.
              </span>
            </label>

            <Boton
              onClick={lanzarPrueba}
              disabled={!autenticado || ocupado !== null}
              className="w-full"
            >
              {ocupado === "carga" ? "Ejecutando…" : "Ejecutar prueba de carga"}
            </Boton>

            <div className="border-t border-borde-suave pt-4">
              <Campo
                etiqueta="Comparativa de hilos"
                ayuda="Repite la misma carga con cada configuración; la serie completa puede tardar cerca de un minuto"
              >
                <input
                  value={configuraciones}
                  onChange={(e) => setConfiguraciones(e.target.value)}
                  placeholder="1,2,4,8,16,32,64"
                  className={claseEntrada}
                />
              </Campo>
              <Boton
                variante="secundario"
                onClick={lanzarComparativa}
                disabled={!autenticado || ocupado !== null}
                className="mt-3 w-full"
              >
                {ocupado === "comparativa" ? "Comparando…" : "Ejecutar comparativa"}
              </Boton>
            </div>
          </div>
        </Tarjeta>

        <div className="min-w-0 space-y-4">
          {comparativa && (
            <Tarjeta
              titulo="Comparativa de configuraciones"
              descripcion={`${comparativa.solicitudes} solicitudes por configuración · modo ${comparativa.modo.replace("_", " ")}`}
            >
              <GraficaComparativa corridas={comparativa.corridas} />
              <div className="mt-4 rounded-lg border border-acento/25 bg-acento/5 px-4 py-3 text-xs leading-relaxed text-texto-suave">
                <b className="text-acento">Lectura de los resultados. </b>
                {comparativa.conclusion}
              </div>
              <div className="mt-4">
                <Tabla
                  columnas={[
                    "Hilos",
                    "Tiempo",
                    "Solicitudes/s",
                    "Latencia media",
                    "p95",
                    "Espera en cola",
                    "Pico",
                    "Aceleración",
                  ]}
                >
                  {comparativa.corridas.map((c) => (
                    <tr
                      key={c.hilos}
                      className={
                        c.hilos === comparativa.mejor_configuracion
                          ? "bg-exito/5"
                          : "hover:bg-superficie-2/50"
                      }
                    >
                      <td className="px-3 py-2 font-mono text-hilo">{c.hilos}</td>
                      <td className="px-3 py-2 font-mono">{c.tiempo_total_s.toFixed(3)} s</td>
                      <td className="px-3 py-2 font-mono">{c.throughput_rps}</td>
                      <td className="px-3 py-2 font-mono text-texto-suave">
                        {c.latencia_promedio_ms} ms
                      </td>
                      <td className="px-3 py-2 font-mono text-texto-suave">
                        {c.latencia_p95_ms} ms
                      </td>
                      <td className="px-3 py-2 font-mono text-texto-suave">
                        {c.espera_promedio_ms} ms
                      </td>
                      <td className="px-3 py-2 font-mono">{c.pico_concurrencia}</td>
                      <td className="px-3 py-2 font-mono text-acento">
                        x{c.detalle.aceleracion}
                      </td>
                    </tr>
                  ))}
                </Tabla>
              </div>
            </Tarjeta>
          )}

          {ultima && (
            <Tarjeta titulo="Última prueba de carga" descripcion={ultima.etiqueta}>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <Metrica
                  titulo="Tiempo total"
                  valor={ultima.tiempo_total_s.toFixed(3)}
                  unidad="s"
                  tono="acento"
                  detalle={`Secuencial estimado: ${ultima.detalle.tiempo_secuencial_estimado_s} s`}
                />
                <Metrica
                  titulo="Throughput"
                  valor={ultima.throughput_rps}
                  unidad="sol/s"
                  detalle={`${ultima.exitosas} exitosas · ${ultima.fallidas} fallidas`}
                />
                <Metrica
                  titulo="Aceleración"
                  valor={`x${ultima.detalle.aceleracion}`}
                  tono="hilo"
                  detalle={`Eficiencia por hilo: ${ultima.detalle.eficiencia_por_hilo}`}
                />
                <Metrica
                  titulo="Pico de concurrencia"
                  valor={ultima.pico_concurrencia}
                  detalle={`${ultima.hilos_utilizados.length} hilos distintos`}
                />
              </div>
              {ultima.detalle.errores.length > 0 && (
                <div className="mt-3">
                  <Aviso>{ultima.detalle.errores.join(" · ")}</Aviso>
                </div>
              )}
            </Tarjeta>
          )}

          <Tarjeta
            titulo="Reparto del trabajo entre hilos"
            descripcion="Cada fila es una tarea: qué hilo la tomó, cuánto esperó en cola y cuántos hilos trabajaban en ese momento."
          >
            {mediciones.length === 0 ? (
              <Vacio mensaje="Todavía no se ha procesado ninguna solicitud." />
            ) : (
              <Tabla
                columnas={["Referencia", "Hilo", "Espera", "Procesamiento", "Concurrencia"]}
              >
                {mediciones.slice(0, 18).map((m, i) => (
                  <tr key={`${m.referencia}-${i}`} className="hover:bg-superficie-2/50">
                    <td className="px-3 py-2 font-mono text-texto-suave">{m.referencia}</td>
                    <td className="px-3 py-2">
                      <Etiqueta tono="hilo">{m.hilo}</Etiqueta>
                    </td>
                    <td className="px-3 py-2 font-mono text-texto-suave">{m.espera_ms} ms</td>
                    <td className="px-3 py-2 font-mono">{m.procesamiento_ms} ms</td>
                    <td className="px-3 py-2 font-mono text-acento">
                      {m.concurrencia_observada} / {m.hilos_configurados}
                    </td>
                  </tr>
                ))}
              </Tabla>
            )}
          </Tarjeta>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Tarjeta
          titulo="Historial de pruebas"
          descripcion="Registro persistente de cada corrida, para comparar el comportamiento antes y después de un ajuste."
        >
          {historial.length === 0 ? (
            <Vacio mensaje="Aún no se han registrado pruebas." />
          ) : (
            <Tabla columnas={["Etiqueta", "Solicitudes", "Hilos", "Tiempo", "Sol/s"]}>
              {historial.map((h) => (
                <tr key={h.id} className="hover:bg-superficie-2/50">
                  <td className="px-3 py-2 text-texto-suave">{h.etiqueta}</td>
                  <td className="px-3 py-2 font-mono">{h.solicitudes}</td>
                  <td className="px-3 py-2 font-mono text-hilo">{h.hilos}</td>
                  <td className="px-3 py-2 font-mono">{h.tiempo_total_s.toFixed(3)} s</td>
                  <td className="px-3 py-2 font-mono text-acento">{h.throughput_rps}</td>
                </tr>
              ))}
            </Tabla>
          )}
        </Tarjeta>

        <Tarjeta
          titulo="Hilos vivos en el proceso"
          descripcion="Hilos del pool más los propios del servidor. Evidencia que la concurrencia ocurre dentro de un único proceso."
        >
          {!estado ? (
            <Cargador filas={2} />
          ) : (
            <>
              <div className="flex flex-wrap gap-1.5">
                {/* Los nombres de hilo pueden repetirse (p. ej. los del servidor),
                    por eso la clave incluye la posición. */}
                {estado.hilos_del_proceso.map((h, i) => (
                  <Etiqueta
                    key={`${h}-${i}`}
                    tono={h.startsWith("solicitud-worker") ? "hilo" : "neutro"}
                  >
                    {h}
                  </Etiqueta>
                ))}
              </div>
              <div className="mt-4 border-t border-borde-suave pt-4">
                <p className="mb-2 text-[11px] uppercase tracking-wider text-texto-tenue">
                  Llamadas coordinadas por el Mediator
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {Object.entries(estado.mediador.llamadas_por_colega).map(([k, v]) => (
                    <Etiqueta key={k} tono="acento">
                      {k}: {v}
                    </Etiqueta>
                  ))}
                </div>
              </div>
            </>
          )}
        </Tarjeta>
      </div>
    </>
  );
}
