"use client";

/** Servicio de Muestras (Nodo 4). Registro y estado de las muestras. */

import { useCallback, useState } from "react";
import { Encabezado } from "@/components/Encabezado";
import {
  Aviso,
  Boton,
  Campo,
  Cargador,
  Etiqueta,
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
import type { Cliente, Muestra } from "@/lib/tipos";

const TIPOS = ["sangre", "orina", "tejido", "saliva", "hisopado", "otro"];

export default function Muestras() {
  const { autenticado } = useSesion();
  const [errorFormulario, setErrorFormulario] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const [formulario, setFormulario] = useState({
    codigo: "",
    cliente_id: "",
    tipo: "sangre",
    descripcion: "",
  });

  const consultar = useCallback(async () => {
    const [muestras, clientes] = await Promise.all([
      api.get<Muestra[]>("/api/muestras"),
      api.get<Cliente[]>("/api/clientes"),
    ]);
    return { muestras, clientes };
  }, []);

  const { datos, error: errorConsulta, recargar } = useSondeo(consultar, 7000);
  const muestras = datos?.muestras ?? null;
  const clientes = datos?.clientes ?? [];
  const error = errorFormulario ?? errorConsulta;

  // El selector toma el primer cliente disponible mientras no se elija otro.
  const clienteElegido = formulario.cliente_id || clientes[0]?.id || "";

  function sugerirCodigo() {
    const fecha = new Date();
    const sello = `${fecha.getHours()}${fecha.getMinutes()}${fecha.getSeconds()}`;
    setFormulario((f) => ({ ...f, codigo: `MU-${fecha.getFullYear()}-${sello}` }));
  }

  async function registrar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setErrorFormulario(null);
    try {
      await api.post("/api/muestras", { ...formulario, cliente_id: clienteElegido });
      setFormulario((f) => ({ ...f, codigo: "", descripcion: "" }));
      recargar();
    } catch (err) {
      setErrorFormulario(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setEnviando(false);
    }
  }

  const nombreCliente = (id: string) =>
    clientes.find((c) => c.id === id)?.nombre ?? id.slice(0, 8);

  return (
    <>
      <Encabezado
        nodo="Nodo 4 · Servicio de Muestras"
        titulo="Muestras"
        descripcion="El estado de cada muestra lo actualiza el Mediator del Servicio de Solicitudes: pasa a 'en análisis' cuando un hilo la toma y a 'procesada' cuando el resultado queda registrado."
      />

      <div className="grid gap-4 lg:grid-cols-[330px_1fr]">
        <Tarjeta titulo="Registrar muestra">
          <form onSubmit={registrar} className="space-y-3.5">
            <Campo etiqueta="Código de la muestra">
              <div className="flex gap-2">
                <input
                  value={formulario.codigo}
                  onChange={(e) => setFormulario({ ...formulario, codigo: e.target.value })}
                  className={claseEntrada}
                  required
                  minLength={3}
                  placeholder="MU-2026-0001"
                />
                <Boton variante="secundario" onClick={sugerirCodigo}>
                  Generar
                </Boton>
              </div>
            </Campo>
            <Campo etiqueta="Cliente">
              <select
                value={clienteElegido}
                onChange={(e) => setFormulario({ ...formulario, cliente_id: e.target.value })}
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
            <Campo etiqueta="Tipo">
              <select
                value={formulario.tipo}
                onChange={(e) => setFormulario({ ...formulario, tipo: e.target.value })}
                className={claseEntrada}
              >
                {TIPOS.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </Campo>
            <Campo etiqueta="Descripción">
              <input
                value={formulario.descripcion}
                onChange={(e) => setFormulario({ ...formulario, descripcion: e.target.value })}
                className={claseEntrada}
              />
            </Campo>
            {error && <Aviso>{error}</Aviso>}
            {!autenticado && <Aviso tono="alerta">Inicie sesión para registrar muestras.</Aviso>}
            <Boton tipo="submit" disabled={enviando || !autenticado} className="w-full">
              {enviando ? "Registrando…" : "Registrar"}
            </Boton>
          </form>
        </Tarjeta>

        <Tarjeta
          titulo="Muestras recibidas"
          descripcion={muestras ? `${muestras.length} registros` : undefined}
        >
          {!muestras ? (
            <Cargador />
          ) : muestras.length === 0 ? (
            <Vacio mensaje="Aún no se han registrado muestras." />
          ) : (
            <Tabla columnas={["Código", "Cliente", "Tipo", "Estado", "Recepción"]}>
              {muestras.map((m) => (
                <tr key={m.id} className="hover:bg-superficie-2/50">
                  <td className="px-3 py-2 font-mono text-acento">{m.codigo}</td>
                  <td className="px-3 py-2">{nombreCliente(m.cliente_id)}</td>
                  <td className="px-3 py-2 text-texto-suave">{m.tipo}</td>
                  <td className="px-3 py-2">
                    <Etiqueta tono={estadoTono(m.estado)}>{m.estado.replace("_", " ")}</Etiqueta>
                  </td>
                  <td className="px-3 py-2 font-mono text-texto-tenue">{fecha(m.recibida_en)}</td>
                </tr>
              ))}
            </Tabla>
          )}
        </Tarjeta>
      </div>
    </>
  );
}
