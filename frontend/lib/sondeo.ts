"use client";

/**
 * Hook de consulta periódica al backend.
 *
 * Las vistas del panel muestran estado vivo (nodos, hilos, eventos), así que
 * casi todas necesitan lo mismo: cargar al montar, repetir cada cierto tiempo y
 * poder recargar tras una acción del usuario.
 *
 * El estado se asigna solo después de que la promesa resuelve y únicamente si
 * el componente sigue montado: de otro modo, navegar entre páginas durante un
 * sondeo dejaría actualizaciones huérfanas.
 */

import { useCallback, useEffect, useState } from "react";

interface Resultado<T> {
  datos: T | null;
  error: string | null;
  cargando: boolean;
  recargar: () => void;
}

export function useSondeo<T>(
  obtener: () => Promise<T>,
  intervaloMs = 0,
): Resultado<T> {
  const [datos, setDatos] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cargando, setCargando] = useState(true);

  // Una recarga manual solo incrementa este contador; el efecto hace el resto.
  const [version, setVersion] = useState(0);
  const recargar = useCallback(() => setVersion((v) => v + 1), []);

  useEffect(() => {
    let vivo = true;

    const correr = async () => {
      try {
        const resultado = await obtener();
        if (!vivo) return;
        setDatos(resultado);
        setError(null);
      } catch (e) {
        if (vivo) setError(e instanceof Error ? e.message : "Error desconocido");
      } finally {
        if (vivo) setCargando(false);
      }
    };

    void correr();
    if (intervaloMs <= 0) {
      return () => {
        vivo = false;
      };
    }

    const temporizador = setInterval(() => void correr(), intervaloMs);
    return () => {
      vivo = false;
      clearInterval(temporizador);
    };
  }, [obtener, intervaloMs, version]);

  return { datos, error, cargando, recargar };
}
