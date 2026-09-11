import type { ReactNode } from "react";

/** Encabezado de página con su lugar dentro de la arquitectura. */
export function Encabezado({
  titulo,
  descripcion,
  nodo,
  accion,
}: {
  titulo: string;
  descripcion: ReactNode;
  nodo?: string;
  accion?: ReactNode;
}) {
  return (
    <header className="mb-7 flex flex-wrap items-start justify-between gap-4">
      <div className="max-w-2xl">
        {nodo && (
          <p className="mb-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-acento">
            {nodo}
          </p>
        )}
        <h1 className="text-2xl font-semibold tracking-tight">{titulo}</h1>
        <p className="mt-1.5 text-sm leading-relaxed text-texto-suave">{descripcion}</p>
      </div>
      {accion}
    </header>
  );
}
