"use client";

/**
 * Gráfica de la comparativa de hilos.
 *
 * Dos series sobre el mismo eje de configuraciones: el tiempo total (barras,
 * menos es mejor) y la aceleración obtenida frente al procesamiento secuencial
 * (línea). Es la lectura que sustenta la evaluación de escalabilidad.
 */

import type { CorridaPrueba } from "@/lib/tipos";

export function GraficaComparativa({ corridas }: { corridas: CorridaPrueba[] }) {
  if (!corridas.length) return null;

  // El lienzo crece con la cantidad de configuraciones para que las barras y
  // sus etiquetas no se aprieten cuando la serie llega hasta 64 hilos.
  const ancho = Math.max(640, corridas.length * 92);
  const alto = 240;
  const margen = { arriba: 18, derecha: 46, abajo: 34, izquierda: 46 };
  const areaAncho = ancho - margen.izquierda - margen.derecha;
  const areaAlto = alto - margen.arriba - margen.abajo;

  const maxTiempo = Math.max(...corridas.map((c) => c.tiempo_total_s)) * 1.15 || 1;
  const maxAcel = Math.max(...corridas.map((c) => c.detalle.aceleracion), 1) * 1.15;

  const paso = areaAncho / corridas.length;
  const anchoBarra = Math.min(52, paso * 0.5);

  const puntos = corridas.map((c, i) => ({
    x: margen.izquierda + paso * i + paso / 2,
    yTiempo: margen.arriba + areaAlto - (c.tiempo_total_s / maxTiempo) * areaAlto,
    yAcel: margen.arriba + areaAlto - (c.detalle.aceleracion / maxAcel) * areaAlto,
    corrida: c,
  }));

  const linea = puntos.map((p) => `${p.x},${p.yAcel}`).join(" ");

  return (
    <div className="-mx-5 overflow-x-auto px-5">
      <svg
        viewBox={`0 0 ${ancho} ${alto}`}
        className="h-auto w-full"
        style={{ minWidth: Math.min(ancho, 560) }}
        role="img"
        aria-label="Comparación de tiempo total y aceleración según la cantidad de hilos"
      >
        {[0, 0.25, 0.5, 0.75, 1].map((f) => {
          const y = margen.arriba + areaAlto * (1 - f);
          return (
            <g key={f}>
              <line
                x1={margen.izquierda}
                x2={ancho - margen.derecha}
                y1={y}
                y2={y}
                stroke="var(--color-borde-suave)"
                strokeWidth={1}
              />
              <text
                x={margen.izquierda - 8}
                y={y + 3.5}
                textAnchor="end"
                className="fill-[var(--color-texto-tenue)] text-[9px]"
              >
                {(maxTiempo * f).toFixed(1)}s
              </text>
              <text
                x={ancho - margen.derecha + 8}
                y={y + 3.5}
                className="fill-[var(--color-hilo)] text-[9px]"
              >
                x{(maxAcel * f).toFixed(1)}
              </text>
            </g>
          );
        })}

        {puntos.map((p) => (
          <g key={p.corrida.hilos}>
            <rect
              x={p.x - anchoBarra / 2}
              y={p.yTiempo}
              width={anchoBarra}
              height={margen.arriba + areaAlto - p.yTiempo}
              rx={4}
              fill="var(--color-acento)"
              opacity={0.75}
            />
            <text
              x={p.x}
              y={p.yTiempo - 6}
              textAnchor="middle"
              className="fill-[var(--color-texto)] text-[9px] font-medium"
            >
              {p.corrida.tiempo_total_s.toFixed(2)}s
            </text>
            <text
              x={p.x}
              y={alto - 12}
              textAnchor="middle"
              className="fill-[var(--color-texto-suave)] text-[10px]"
            >
              {p.corrida.hilos} {p.corrida.hilos === 1 ? "hilo" : "hilos"}
            </text>
          </g>
        ))}

        <polyline
          points={linea}
          fill="none"
          stroke="var(--color-hilo)"
          strokeWidth={2}
          strokeLinejoin="round"
        />
        {puntos.map((p) => (
          <circle
            key={`p-${p.corrida.hilos}`}
            cx={p.x}
            cy={p.yAcel}
            r={3.5}
            fill="var(--color-fondo)"
            stroke="var(--color-hilo)"
            strokeWidth={2}
          />
        ))}
      </svg>

      <div className="mt-2 flex flex-wrap items-center gap-4 text-[11px] text-texto-suave">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm bg-acento/75" /> Tiempo total (menor es mejor)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-0.5 w-4 bg-hilo" /> Aceleración frente al procesamiento secuencial
        </span>
      </div>
    </div>
  );
}
