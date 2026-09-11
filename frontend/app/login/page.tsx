"use client";

/** Autenticación contra el Servicio de Usuarios, a través del API Gateway. */

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Encabezado } from "@/components/Encabezado";
import { Aviso, Boton, Campo, Tarjeta, claseEntrada } from "@/components/ui";
import { useSesion } from "@/components/Sesion";

const CUENTAS = [
  { email: "admin@labcloud.co", clave: "admin123", rol: "Administrador" },
  { email: "recepcion@labcloud.co", clave: "labcloud", rol: "Recepcionista" },
  { email: "analista@labcloud.co", clave: "labcloud", rol: "Analista" },
];

export default function Login() {
  const { entrar, autenticado, usuario, salir } = useSesion();
  const router = useRouter();
  const [email, setEmail] = useState(CUENTAS[1].email);
  const [clave, setClave] = useState(CUENTAS[1].clave);
  const [error, setError] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: React.FormEvent) {
    e.preventDefault();
    setEnviando(true);
    setError(null);
    try {
      await entrar(email, clave);
      router.push("/solicitudes");
    } catch (err) {
      setError(err instanceof Error ? err.message : "No fue posible iniciar sesión");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <>
      <Encabezado
        nodo="Nodo 1 · Servicio de Usuarios"
        titulo="Acceso al sistema"
        descripcion="El Servicio de Usuarios emite el token y el API Gateway lo valida antes de dirigir cualquier operación de escritura hacia los servicios internos."
      />

      <div className="grid max-w-3xl gap-4 md:grid-cols-2">
        <Tarjeta titulo="Credenciales">
          {autenticado ? (
            <div className="space-y-4">
              <Aviso tono="exito">
                Sesión activa como <b>{usuario?.nombre}</b> ({usuario?.rol}).
              </Aviso>
              <Boton variante="secundario" onClick={salir}>
                Cerrar sesión
              </Boton>
            </div>
          ) : (
            <form onSubmit={enviar} className="space-y-4">
              <Campo etiqueta="Correo">
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={claseEntrada}
                  required
                />
              </Campo>
              <Campo etiqueta="Contraseña">
                <input
                  type="password"
                  value={clave}
                  onChange={(e) => setClave(e.target.value)}
                  className={claseEntrada}
                  required
                />
              </Campo>
              {error && <Aviso>{error}</Aviso>}
              <Boton tipo="submit" disabled={enviando} className="w-full">
                {enviando ? "Verificando…" : "Entrar"}
              </Boton>
            </form>
          )}
        </Tarjeta>

        <Tarjeta
          titulo="Cuentas de demostración"
          descripcion="Creadas por el Servicio de Usuarios en su primer arranque."
        >
          <ul className="space-y-2">
            {CUENTAS.map((c) => (
              <li key={c.email}>
                <button
                  onClick={() => {
                    setEmail(c.email);
                    setClave(c.clave);
                  }}
                  className="w-full rounded-lg border border-borde-suave bg-superficie-2/50 px-3.5 py-2.5 text-left transition hover:border-acento/40"
                >
                  <p className="text-[13px] font-medium">{c.rol}</p>
                  <p className="font-mono text-[11px] text-texto-suave">{c.email}</p>
                  <p className="font-mono text-[11px] text-texto-tenue">contraseña: {c.clave}</p>
                </button>
              </li>
            ))}
          </ul>
        </Tarjeta>
      </div>
    </>
  );
}
