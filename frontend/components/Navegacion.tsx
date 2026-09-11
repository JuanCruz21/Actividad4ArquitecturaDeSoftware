"use client";

/**
 * Navegación principal.
 *
 * Refleja la organización del sistema: primero la vista de la arquitectura y
 * después la operación del laboratorio. El indicador superior consulta el
 * estado de los nodos al Gateway cada ocho segundos.
 *
 * En pantallas anchas es una barra lateral; en pantallas estrechas se convierte
 * en una cabecera con los enlaces en una fila desplazable, para que el
 * contenido nunca quede comprimido.
 */

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback } from "react";
import { gateway } from "@/lib/api";
import { useSondeo } from "@/lib/sondeo";
import { useSesion } from "@/components/Sesion";
import type { SaludSistema } from "@/lib/tipos";

const SECCIONES = [
  {
    titulo: "Arquitectura",
    enlaces: [
      { href: "/", texto: "Panel de nodos", icono: "◎" },
      { href: "/concurrencia", texto: "Laboratorio de hilos", icono: "≡" },
    ],
  },
  {
    titulo: "Operación del laboratorio",
    enlaces: [
      { href: "/clientes", texto: "Clientes", icono: "◱" },
      { href: "/muestras", texto: "Muestras", icono: "◈" },
      { href: "/solicitudes", texto: "Solicitudes", icono: "▤" },
      { href: "/resultados", texto: "Resultados", icono: "✓" },
      { href: "/notificaciones", texto: "Eventos", icono: "◇" },
    ],
  },
];

const TODOS = SECCIONES.flatMap((s) => s.enlaces);

function esActivo(ruta: string, href: string): boolean {
  return href === "/" ? ruta === "/" : ruta.startsWith(href);
}

export function Navegacion() {
  const ruta = usePathname();
  const { usuario, autenticado, salir } = useSesion();

  const consultar = useCallback(() => gateway.salud() as Promise<SaludSistema>, []);
  const { datos: salud, error } = useSondeo(consultar, 8000);
  const operativo = salud?.estado_general === "operativo";

  const indicador = (
    <div className="flex items-center gap-2 text-[11px]">
      <span
        className={`latido h-1.5 w-1.5 shrink-0 rounded-full ${
          error ? "bg-error" : !salud ? "bg-texto-tenue" : operativo ? "bg-exito" : "bg-alerta"
        }`}
      />
      <span className="text-texto-suave">
        {error
          ? "Gateway sin respuesta"
          : salud
            ? `${salud.servicios_activos}/${salud.servicios_totales} servicios activos`
            : "Consultando…"}
      </span>
    </div>
  );

  const marca = (
    <Link href="/" className="block shrink-0">
      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-acento">LabCloud</p>
      <p className="text-lg font-semibold leading-tight">Distributed</p>
    </Link>
  );

  const sesion = autenticado ? (
    <div className="min-w-0">
      <p className="truncate text-[13px] font-medium">{usuario?.nombre}</p>
      <p className="truncate text-[11px] text-texto-tenue">{usuario?.rol}</p>
      <button
        onClick={salir}
        className="mt-1 text-[11px] text-texto-suave underline-offset-2 hover:text-error hover:underline"
      >
        Cerrar sesión
      </button>
    </div>
  ) : (
    <Link
      href="/login"
      className="block shrink-0 rounded-lg border border-borde bg-superficie-2 px-3 py-2 text-center text-xs text-texto-suave transition hover:border-acento/50 hover:text-texto"
    >
      Iniciar sesión
    </Link>
  );

  return (
    <>
      {/* Pantallas anchas: barra lateral */}
      <aside className="hidden w-64 shrink-0 flex-col border-r border-borde bg-superficie/60 lg:flex">
        <div className="border-b border-borde px-5 py-5">
          {marca}
          <div className="mt-3">{indicador}</div>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4">
          {SECCIONES.map((seccion) => (
            <div key={seccion.titulo} className="mb-5">
              <p className="px-2 pb-2 text-[10px] font-medium uppercase tracking-[0.14em] text-texto-tenue">
                {seccion.titulo}
              </p>
              <ul className="space-y-0.5">
                {seccion.enlaces.map((enlace) => (
                  <li key={enlace.href}>
                    <Link
                      href={enlace.href}
                      className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] transition ${
                        esActivo(ruta, enlace.href)
                          ? "bg-acento/10 text-acento"
                          : "text-texto-suave hover:bg-superficie-2 hover:text-texto"
                      }`}
                    >
                      <span className="w-4 text-center font-mono text-xs opacity-70">
                        {enlace.icono}
                      </span>
                      {enlace.texto}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        <div className="border-t border-borde px-4 py-4">{sesion}</div>
      </aside>

      {/* Pantallas estrechas: cabecera con enlaces en una fila desplazable */}
      <header className="border-b border-borde bg-superficie/60 lg:hidden">
        <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3">
          {marca}
          <div className="flex flex-wrap items-center justify-end gap-x-4 gap-y-1">
            {indicador}
            {sesion}
          </div>
        </div>
        <nav className="overflow-x-auto px-2 pb-2">
          <ul className="flex min-w-max gap-1">
            {TODOS.map((enlace) => (
              <li key={enlace.href}>
                <Link
                  href={enlace.href}
                  className={`block whitespace-nowrap rounded-lg px-3 py-1.5 text-[13px] transition ${
                    esActivo(ruta, enlace.href)
                      ? "bg-acento/10 text-acento"
                      : "text-texto-suave hover:bg-superficie-2 hover:text-texto"
                  }`}
                >
                  {enlace.texto}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </header>
    </>
  );
}
