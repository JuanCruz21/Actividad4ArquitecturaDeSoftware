"use client";

/** Piezas de interfaz reutilizadas por todas las vistas del panel. */

import type { ReactNode } from "react";

export function Tarjeta({
  titulo,
  descripcion,
  accion,
  children,
  className = "",
}: {
  titulo?: ReactNode;
  descripcion?: ReactNode;
  accion?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    // `min-w-0` es necesario para que la tarjeta pueda encogerse dentro de una
    // rejilla: sin él, una tabla ancha estiraría la columna y desbordaría la
    // página en lugar de desplazarse dentro de su propio contenedor.
    <section
      className={`min-w-0 rounded-xl border border-borde bg-superficie/80 backdrop-blur-sm ${className}`}
    >
      {(titulo || accion) && (
        <header className="flex flex-wrap items-start justify-between gap-3 border-b border-borde-suave px-5 py-4">
          <div>
            {titulo && <h2 className="text-sm font-semibold tracking-wide">{titulo}</h2>}
            {descripcion && (
              <p className="mt-1 text-xs leading-relaxed text-texto-suave">{descripcion}</p>
            )}
          </div>
          {accion}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

type Tono = "neutro" | "exito" | "alerta" | "error" | "acento" | "evento" | "hilo";

const TONOS: Record<Tono, string> = {
  neutro: "border-borde bg-superficie-2 text-texto-suave",
  exito: "border-exito/30 bg-exito/10 text-exito",
  alerta: "border-alerta/30 bg-alerta/10 text-alerta",
  error: "border-error/30 bg-error/10 text-error",
  acento: "border-acento/30 bg-acento/10 text-acento",
  evento: "border-evento/30 bg-evento/10 text-evento",
  hilo: "border-hilo/30 bg-hilo/10 text-hilo",
};

export function Etiqueta({
  children,
  tono = "neutro",
  className = "",
}: {
  children: ReactNode;
  tono?: Tono;
  className?: string;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 text-[11px] font-medium ${TONOS[tono]} ${className}`}
    >
      {children}
    </span>
  );
}

export function Boton({
  children,
  onClick,
  tipo = "button",
  variante = "primario",
  disabled,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  tipo?: "button" | "submit";
  variante?: "primario" | "secundario" | "peligro" | "fantasma";
  disabled?: boolean;
  className?: string;
}) {
  const variantes = {
    primario:
      "bg-acento-fuerte text-[#03121c] hover:bg-acento font-semibold shadow-[0_0_0_1px_rgba(56,189,248,0.35)]",
    secundario: "border border-borde bg-superficie-2 text-texto hover:border-acento/50",
    peligro: "border border-error/40 bg-error/10 text-error hover:bg-error/20",
    fantasma: "text-texto-suave hover:text-texto",
  } as const;
  return (
    <button
      type={tipo}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-3.5 py-2 text-xs transition disabled:cursor-not-allowed disabled:opacity-45 ${variantes[variante]} ${className}`}
    >
      {children}
    </button>
  );
}

export function Campo({
  etiqueta,
  ayuda,
  children,
}: {
  etiqueta: string;
  ayuda?: string;
  children: ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-texto-tenue">
        {etiqueta}
      </span>
      {children}
      {ayuda && <span className="mt-1 block text-[11px] text-texto-tenue">{ayuda}</span>}
    </label>
  );
}

export const claseEntrada =
  "w-full rounded-lg border border-borde bg-fondo/70 px-3 py-2 text-sm text-texto outline-none transition placeholder:text-texto-tenue focus:border-acento/60 focus:ring-2 focus:ring-acento/15";

export function Metrica({
  titulo,
  valor,
  unidad,
  detalle,
  tono = "neutro",
}: {
  titulo: string;
  valor: ReactNode;
  unidad?: string;
  detalle?: ReactNode;
  tono?: Tono;
}) {
  const color = {
    neutro: "text-texto",
    exito: "text-exito",
    alerta: "text-alerta",
    error: "text-error",
    acento: "text-acento",
    evento: "text-evento",
    hilo: "text-hilo",
  }[tono];
  return (
    <div className="rounded-lg border border-borde-suave bg-superficie-2/60 px-4 py-3">
      <p className="text-[11px] uppercase tracking-wider text-texto-tenue">{titulo}</p>
      <p className={`mt-1 font-mono text-2xl font-semibold tabular-nums ${color}`}>
        {valor}
        {unidad && <span className="ml-1 text-sm font-normal text-texto-tenue">{unidad}</span>}
      </p>
      {detalle && <p className="mt-1 text-[11px] text-texto-suave">{detalle}</p>}
    </div>
  );
}

export function Vacio({ mensaje }: { mensaje: string }) {
  return (
    <p className="rounded-lg border border-dashed border-borde px-4 py-8 text-center text-xs text-texto-tenue">
      {mensaje}
    </p>
  );
}

export function Cargador({ filas = 3 }: { filas?: number }) {
  return (
    <div className="space-y-2">
      {Array.from({ length: filas }).map((_, i) => (
        <div key={i} className="cargando h-9 rounded-lg" />
      ))}
    </div>
  );
}

export function Aviso({
  children,
  tono = "error",
}: {
  children: ReactNode;
  tono?: "error" | "exito" | "alerta" | "acento";
}) {
  const tonos = {
    error: "border-error/30 bg-error/10 text-error",
    exito: "border-exito/30 bg-exito/10 text-exito",
    alerta: "border-alerta/30 bg-alerta/10 text-alerta",
    acento: "border-acento/30 bg-acento/10 text-acento",
  };
  return (
    <div className={`rounded-lg border px-3.5 py-2.5 text-xs ${tonos[tono]}`}>{children}</div>
  );
}

/** Tabla con desplazamiento horizontal propio: la página nunca se desborda. */
export function Tabla({
  columnas,
  children,
}: {
  columnas: string[];
  children: ReactNode;
}) {
  return (
    <div className="-mx-5 overflow-x-auto px-5">
      <table className="w-full min-w-[640px] border-collapse text-left text-xs">
        <thead>
          <tr className="border-b border-borde">
            {columnas.map((c) => (
              <th
                key={c}
                className="whitespace-nowrap px-3 py-2 text-[11px] font-medium uppercase tracking-wider text-texto-tenue"
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-borde-suave">{children}</tbody>
      </table>
    </div>
  );
}

export function estadoTono(estado: string): Tono {
  switch (estado) {
    case "resultado_disponible":
    case "procesada":
    case "entregado":
    case "activo":
    case "enviada":
    case "operativo":
      return "exito";
    case "en_proceso":
    case "en_analisis":
      return "acento";
    case "en_cola":
    case "recibida":
    case "registrada":
    case "degradado":
      return "alerta";
    case "fallida":
    case "fallido":
    case "descartada":
    case "inactivo":
      return "error";
    default:
      return "neutro";
  }
}

export function fecha(valor?: string): string {
  if (!valor) return "—";
  const d = new Date(valor);
  return d.toLocaleString("es-CO", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
