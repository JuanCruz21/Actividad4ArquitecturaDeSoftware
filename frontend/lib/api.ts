/**
 * Cliente HTTP del frontend.
 *
 * Todas las peticiones salen hacia el **API Gateway**: el navegador nunca
 * conoce los puertos de los servicios internos. Esa es, precisamente, la
 * propiedad que aporta el patrón Proxy en el lado del cliente.
 */

export const GATEWAY =
  process.env.NEXT_PUBLIC_GATEWAY_URL ?? "http://127.0.0.1:8000";

const CLAVE_TOKEN = "labcloud.token";
const CLAVE_USUARIO = "labcloud.usuario";

export class ErrorApi extends Error {
  constructor(
    readonly estado: number,
    mensaje: string,
    readonly servicio?: string | null,
  ) {
    super(mensaje);
    this.name = "ErrorApi";
  }
}

/* --- Sesión como almacén externo -----------------------------------------
 * La sesión vive en `localStorage`, que no existe durante el renderizado en el
 * servidor. Se expone como un almacén suscribible para que React la lea con
 * `useSyncExternalStore`: así el primer render del servidor y el del cliente
 * coinciden, y cualquier cambio —incluido el hecho desde otra pestaña— se
 * propaga solo.
 */

const oyentes = new Set<() => void>();

// `getSnapshot` debe devolver siempre la misma referencia mientras el dato no
// cambie; por eso se memoriza el texto original junto al objeto ya convertido.
let cacheCrudo: string | null = null;
let cacheUsuario: unknown = null;

function notificar() {
  for (const oyente of oyentes) oyente();
}

export function suscribirSesion(alCambiar: () => void): () => void {
  oyentes.add(alCambiar);
  window.addEventListener("storage", alCambiar);
  return () => {
    oyentes.delete(alCambiar);
    window.removeEventListener("storage", alCambiar);
  };
}

export function leerToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(CLAVE_TOKEN);
}

export function usuarioEnSesion<T>(): T | null {
  if (typeof window === "undefined") return null;
  const crudo = window.localStorage.getItem(CLAVE_USUARIO);
  if (crudo !== cacheCrudo) {
    cacheCrudo = crudo;
    cacheUsuario = crudo ? JSON.parse(crudo) : null;
  }
  return cacheUsuario as T | null;
}

export function guardarSesion(token: string, usuario: unknown) {
  window.localStorage.setItem(CLAVE_TOKEN, token);
  window.localStorage.setItem(CLAVE_USUARIO, JSON.stringify(usuario));
  notificar();
}

export function borrarSesion() {
  window.localStorage.removeItem(CLAVE_TOKEN);
  window.localStorage.removeItem(CLAVE_USUARIO);
  notificar();
}

function mensajeDeError(cuerpo: unknown, estado: number): string {
  if (typeof cuerpo === "string" && cuerpo) return cuerpo;
  if (cuerpo && typeof cuerpo === "object") {
    const detalle = (cuerpo as { detail?: unknown }).detail;
    if (typeof detalle === "string") return detalle;
    if (detalle && typeof detalle === "object") {
      const d = detalle as { mensaje?: string; detalle?: string };
      if (d.mensaje) return d.detalle ? `${d.mensaje} — ${d.detalle}` : d.mensaje;
    }
    if (Array.isArray(detalle) && detalle.length) {
      const primero = detalle[0] as { loc?: string[]; msg?: string };
      const campo = primero.loc?.slice(1).join(".") ?? "";
      return campo ? `${campo}: ${primero.msg}` : String(primero.msg);
    }
  }
  return `Error ${estado} al comunicarse con el sistema`;
}

async function peticion<T>(
  ruta: string,
  opciones: RequestInit = {},
): Promise<T> {
  const token = leerToken();
  const encabezados: Record<string, string> = {
    ...(opciones.body ? { "Content-Type": "application/json" } : {}),
    ...((opciones.headers as Record<string, string>) ?? {}),
  };
  if (token) encabezados.Authorization = `Bearer ${token}`;

  let respuesta: Response;
  try {
    respuesta = await fetch(`${GATEWAY}${ruta}`, {
      ...opciones,
      headers: encabezados,
      cache: "no-store",
    });
  } catch {
    throw new ErrorApi(
      0,
      `No se pudo contactar al API Gateway (${GATEWAY}). Verifique que los servicios estén en ejecución.`,
    );
  }

  const servicio = respuesta.headers.get("x-servicio-origen");
  if (respuesta.status === 204) return undefined as T;

  const texto = await respuesta.text();
  let cuerpo: unknown = texto;
  try {
    cuerpo = texto ? JSON.parse(texto) : null;
  } catch {
    /* la respuesta no era JSON */
  }

  if (!respuesta.ok) {
    throw new ErrorApi(respuesta.status, mensajeDeError(cuerpo, respuesta.status), servicio);
  }
  return cuerpo as T;
}

export const api = {
  get: <T>(ruta: string) => peticion<T>(ruta),
  post: <T>(ruta: string, datos?: unknown) =>
    peticion<T>(ruta, { method: "POST", body: JSON.stringify(datos ?? {}) }),
  put: <T>(ruta: string, datos?: unknown) =>
    peticion<T>(ruta, { method: "PUT", body: JSON.stringify(datos ?? {}) }),
  patch: <T>(ruta: string, datos?: unknown) =>
    peticion<T>(ruta, { method: "PATCH", body: JSON.stringify(datos ?? {}) }),
  delete: <T>(ruta: string) => peticion<T>(ruta, { method: "DELETE" }),
};

/** Endpoints propios del Gateway (no se reenvían a ningún servicio). */
export const gateway = {
  salud: () => api.get("/salud"),
  arquitectura: () => api.get("/arquitectura"),
  metricas: () => api.get("/metricas"),
};
