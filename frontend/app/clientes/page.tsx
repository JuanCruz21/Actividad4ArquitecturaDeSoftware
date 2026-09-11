"use client";

/** Servicio de Clientes (Nodo 4). Datos maestros del laboratorio. */

import { useCallback, useState } from "react";
import { Encabezado } from "@/components/Encabezado";
import {
  Aviso,
  Boton,
  Campo,
  Cargador,
  Tabla,
  Tarjeta,
  Vacio,
  claseEntrada,
  fecha,
} from "@/components/ui";
import { api } from "@/lib/api";
import { useSondeo } from "@/lib/sondeo";
import { useSesion } from "@/components/Sesion";
import type { Cliente } from "@/lib/tipos";

const VACIO = { documento: "", nombre: "", email: "", telefono: "", ciudad: "" };

export default function Clientes() {
  const { autenticado } = useSesion();
  const [formulario, setFormulario] = useState(VACIO);
  const [errorFormulario, setErrorFormulario] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  const consultar = useCallback(() => api.get<Cliente[]>("/api/clientes"), []);
  const { datos: clientes, error: errorConsulta, recargar } = useSondeo(consultar);
  const error = errorFormulario ?? errorConsulta;

  async function registrar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setErrorFormulario(null);
    try {
      await api.post("/api/clientes", formulario);
      setFormulario(VACIO);
      recargar();
    } catch (err) {
      setErrorFormulario(err instanceof Error ? err.message : "Error desconocido");
    } finally {
      setEnviando(false);
    }
  }

  const campo = (k: keyof typeof VACIO) => ({
    value: formulario[k],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) =>
      setFormulario({ ...formulario, [k]: e.target.value }),
    className: claseEntrada,
  });

  return (
    <>
      <Encabezado
        nodo="Nodo 4 · Servicio de Clientes"
        titulo="Clientes"
        descripcion="Servicio con base de datos propia. El Servicio de Solicitudes lo consulta a través del Mediator para validar el cliente antes de aceptar un análisis."
      />

      <div className="grid gap-4 lg:grid-cols-[330px_1fr]">
        <Tarjeta titulo="Registrar cliente">
          <form onSubmit={registrar} className="space-y-3.5">
            <Campo etiqueta="Documento o NIT">
              <input {...campo("documento")} required minLength={4} placeholder="CC-1032456789" />
            </Campo>
            <Campo etiqueta="Nombre o razón social">
              <input {...campo("nombre")} required minLength={2} />
            </Campo>
            <Campo etiqueta="Correo">
              <input {...campo("email")} type="email" required />
            </Campo>
            <Campo etiqueta="Teléfono">
              <input {...campo("telefono")} />
            </Campo>
            <Campo etiqueta="Ciudad">
              <input {...campo("ciudad")} />
            </Campo>
            {error && <Aviso>{error}</Aviso>}
            {!autenticado && (
              <Aviso tono="alerta">Inicie sesión para registrar clientes.</Aviso>
            )}
            <Boton tipo="submit" disabled={enviando || !autenticado} className="w-full">
              {enviando ? "Registrando…" : "Registrar"}
            </Boton>
          </form>
        </Tarjeta>

        <Tarjeta
          titulo="Clientes registrados"
          descripcion={clientes ? `${clientes.length} registros en data/clientes.db` : undefined}
        >
          {!clientes ? (
            <Cargador />
          ) : clientes.length === 0 ? (
            <Vacio mensaje="No hay clientes registrados." />
          ) : (
            <Tabla columnas={["Documento", "Nombre", "Correo", "Ciudad", "Registro"]}>
              {clientes.map((c) => (
                <tr key={c.id} className="hover:bg-superficie-2/50">
                  <td className="px-3 py-2 font-mono text-acento">{c.documento}</td>
                  <td className="px-3 py-2">{c.nombre}</td>
                  <td className="max-w-[220px] truncate px-3 py-2 text-texto-suave">{c.email}</td>
                  <td className="px-3 py-2 text-texto-suave">{c.ciudad || "—"}</td>
                  <td className="px-3 py-2 font-mono text-texto-tenue">{fecha(c.creado_en)}</td>
                </tr>
              ))}
            </Tabla>
          )}
        </Tarjeta>
      </div>
    </>
  );
}
