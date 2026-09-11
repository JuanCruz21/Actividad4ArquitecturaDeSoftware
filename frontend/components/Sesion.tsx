"use client";

/**
 * Contexto de sesión.
 *
 * El token emitido por el Servicio de Usuarios se guarda en `localStorage` y se
 * lee con `useSyncExternalStore`, que es la forma segura de consumir un dato
 * que solo existe en el navegador: el render del servidor devuelve `null` y el
 * cliente se sincroniza sin provocar diferencias de hidratación.
 */

import { createContext, useCallback, useContext, useMemo, useSyncExternalStore } from "react";
import type { ReactNode } from "react";
import { api, borrarSesion, guardarSesion, suscribirSesion, usuarioEnSesion } from "@/lib/api";
import type { RespuestaLogin, Usuario } from "@/lib/tipos";

interface ContextoSesion {
  usuario: Usuario | null;
  autenticado: boolean;
  entrar: (email: string, clave: string) => Promise<void>;
  salir: () => void;
}

const Contexto = createContext<ContextoSesion | null>(null);

const sinSesion = () => null;

export function ProveedorSesion({ children }: { children: ReactNode }) {
  const usuario = useSyncExternalStore<Usuario | null>(
    suscribirSesion,
    usuarioEnSesion<Usuario>,
    sinSesion,
  );

  const entrar = useCallback(async (email: string, clave: string) => {
    const datos = await api.post<RespuestaLogin>("/api/auth/login", { email, clave });
    guardarSesion(datos.token, datos.usuario);
  }, []);

  const salir = useCallback(() => borrarSesion(), []);

  const valor = useMemo(
    () => ({ usuario, autenticado: Boolean(usuario), entrar, salir }),
    [usuario, entrar, salir],
  );

  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}

export function useSesion(): ContextoSesion {
  const contexto = useContext(Contexto);
  if (!contexto) throw new Error("useSesion debe usarse dentro de ProveedorSesion");
  return contexto;
}
