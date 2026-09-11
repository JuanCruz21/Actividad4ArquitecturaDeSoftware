/** Tipos del dominio de LabCloud Distributed, espejo de los esquemas del backend. */

export type Rol = "administrador" | "recepcionista" | "analista" | "cliente";

export interface Usuario {
  id: string;
  nombre: string;
  email: string;
  rol: Rol;
  activo: boolean;
  creado_en: string;
}

export interface RespuestaLogin {
  token: string;
  tipo: string;
  expira_en: string;
  usuario: Usuario;
}

export interface Cliente {
  id: string;
  documento: string;
  nombre: string;
  email: string;
  telefono: string;
  ciudad: string;
  activo: boolean;
  creado_en: string;
}

export interface Muestra {
  id: string;
  codigo: string;
  cliente_id: string;
  tipo: string;
  descripcion: string;
  estado: string;
  recibida_en: string;
}

export interface Solicitud {
  id: string;
  codigo: string;
  cliente_id: string;
  cliente_nombre: string;
  cliente_email: string;
  muestra_id: string;
  codigo_muestra: string;
  tipo_analisis: string;
  prioridad: string;
  estado: string;
  observaciones: string;
  resultado_id: string;
  hilo_procesamiento: string;
  espera_cola_ms: number;
  duracion_ms: number;
  intentos: number;
  error: string;
  creada_en: string;
  actualizada_en: string;
}

export interface Resultado {
  id: string;
  solicitud_id: string;
  codigo_solicitud: string;
  cliente_nombre: string;
  cliente_email: string;
  codigo_muestra: string;
  tipo_analisis: string;
  valores: Record<string, { valor: number; unidad: string; rango: string }>;
  diagnostico: string;
  observaciones: string;
  hilo_origen: string;
  duracion_ms: number;
  registrado_en: string;
}

export interface Notificacion {
  id: string;
  evento_id: string;
  tipo_evento: string;
  origen: string;
  destinatario: string;
  canal: string;
  asunto: string;
  mensaje: string;
  estado: string;
  intento_entrega: number;
  recibido_en: string;
}

export interface ServicioSalud {
  id: string;
  nombre: string;
  nodo: string;
  nodo_nombre: string;
  puerto: number;
  url: string;
  patrones: string[];
  alcanzable: boolean;
  estado?: string;
  pid?: number;
  hilos_activos?: number;
  uptime_segundos?: number;
  detalle?: string;
}

export interface SaludSistema {
  estado_general: "operativo" | "degradado";
  servicios_activos: number;
  servicios_totales: number;
  servicios: ServicioSalud[];
  trafico_por_servicio: Record<
    string,
    { peticiones: number; errores: number; latencia_promedio_ms: number; latencia_maxima_ms: number }
  >;
}

export interface Arquitectura {
  sistema: string;
  version: string;
  nodos: {
    id: string;
    nombre: string;
    responsabilidad: string;
    servicios: {
      id: string;
      nombre: string;
      puerto: number;
      url: string;
      descripcion: string;
      patrones: string[];
    }[];
  }[];
  rutas: {
    publica: string;
    servicio: string;
    interna: string;
    requiere_token: boolean;
    descripcion: string;
  }[];
  patrones: { nombre: string; componente: string; aporte: string }[];
  comunicacion: { sincrona: string; asincrona: string; concurrencia: string };
}

export interface EstadoPool {
  hilos_configurados: number;
  solicitudes_en_cola: number;
  solicitudes_en_proceso: number;
  pico_concurrencia: number;
  total_procesadas: number;
  total_fallidas: number;
  hilos_vivos: string[];
}

export interface EstadoConcurrencia {
  pool: EstadoPool;
  mediador: {
    colegas: string[];
    llamadas_por_colega: Record<string, number>;
    total_llamadas: number;
  };
  duracion_analisis_s: number;
  hilos_del_proceso: string[];
}

export interface Medicion {
  referencia: string;
  hilo: string;
  espera_ms: number;
  procesamiento_ms: number;
  total_ms: number;
  concurrencia_observada: number;
  hilos_configurados: number;
  exito: boolean;
  detalle: string;
}

export interface CorridaPrueba {
  id?: string;
  corrida?: string;
  etiqueta: string;
  solicitudes: number;
  hilos: number;
  duracion_analisis_s: number;
  tiempo_total_s: number;
  throughput_rps: number;
  latencia_promedio_ms: number;
  latencia_p95_ms: number;
  latencia_maxima_ms: number;
  espera_promedio_ms: number;
  exitosas: number;
  fallidas: number;
  pico_concurrencia: number;
  hilos_utilizados: string[];
  detalle: {
    modo: string;
    tiempo_secuencial_estimado_s: number;
    aceleracion: number;
    eficiencia_por_hilo: number;
    mejora_vs_primera?: number;
    errores: string[];
  };
  ejecutada_en?: string;
}

export interface Comparativa {
  solicitudes: number;
  configuraciones: number[];
  modo: string;
  corridas: CorridaPrueba[];
  mejor_configuracion: number | null;
  conclusion: string;
}

export interface EstadoEventos {
  origen: string;
  activo: boolean;
  hilos_despachadores: number;
  eventos_en_cola: number;
  eventos_publicados: number;
  eventos_archivados: number;
  observadores: {
    id: string;
    servicio: string;
    tipo_evento: string;
    callback_url: string;
    activa: boolean;
    creada_en: string;
  }[];
}

export interface EntregaEvento {
  evento_id: string;
  tipo: string;
  destino: string;
  estado: string;
  intentos: number;
  detalle: string;
  momento: string;
}
