# LabCloud Distributed

Prototipo de **arquitectura de software distribuida** para la plataforma de
gestión de análisis de laboratorio LabCloud S.A.S.

> **Actividad 4 — Tejiendo redes: arquitectura de software entre hilos y nodos**
> Arquitectura de Software · Ingeniería de Software, octavo semestre
> Corporación Escuela Tecnológica del Oriente · Docente: Edward Villamizar
> Maria Carolina Tafur L. · David Jiménez Sánchez · Juan Manuel Rincón

El sistema separa las funcionalidades de LabCloud en **siete servicios
independientes** que se ejecutan como procesos distintos en puertos propios,
se comunican mediante **REST** y **eventos**, y procesan varias solicitudes de
análisis de forma **concurrente** mediante un conjunto configurable de hilos.

```
Usuario → API Gateway → Servicio de Solicitudes → Hilo del pool →
Servicio de Resultados → evento → Servicio de Notificaciones
```

---

## Puesta en marcha

### Requisitos

| Herramienta | Versión | Para qué |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | 0.5 o superior | Gestor de paquetes y entornos de Python |
| Python | 3.11 o superior | Lo instala `uv` automáticamente si falta |
| Node.js | 20 o superior | Frontend Next.js |

### 1. Backend — los siete servicios

```bash
cd backend
uv sync
uv run python -m labcloud iniciar
```

Un solo comando levanta los siete procesos y muestra sus trazas con un color por
servicio. Cada línea indica el nodo, el proceso y **el hilo** que atiende la
operación, que es la evidencia directa del procesamiento concurrente:

```
[solicitudes  ] 15:53:06 | nodo-2 | solicitudes | pid=49460 | hilo=solicitud-worker_0 | INFO | ▶ SOL-20260911-00001 tomada por solicitud-worker_0 (espera en cola: 0.1 ms, 1 hilo(s) trabajando)
```

### 2. Frontend — panel de control

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

Abrir **http://localhost:3000**.

### Cuentas de demostración

| Correo | Contraseña | Rol |
|---|---|---|
| `admin@labcloud.co` | `admin123` | Administrador |
| `recepcion@labcloud.co` | `labcloud` | Recepcionista |
| `analista@labcloud.co` | `labcloud` | Analista |

---

## Distribución del sistema

| Nodo | Servicio | Puerto | Patrón aplicado |
|---|---|---|---|
| **Nodo 1** — Entrada y acceso | API Gateway | 8000 | **Proxy** |
| | Servicio de Usuarios | 8004 | — |
| **Nodo 2** — Procesamiento | Servicio de Solicitudes | 8001 | **Mediator** + pool de hilos |
| **Nodo 3** — Servicios de soporte | Servicio de Resultados | 8002 | **Observer** (sujeto) |
| | Servicio de Notificaciones | 8003 | **Observer** (observador) |
| **Nodo 4** — Datos maestros | Servicio de Clientes | 8005 | — |
| | Servicio de Muestras | 8006 | — |

Cada servicio tiene **su propia base de datos SQLite** en `backend/data/`.
Ningún servicio lee la base de otro: la información viaja por REST o por eventos.

Comandos útiles del orquestador:

```bash
uv run python -m labcloud estado          # salud de cada nodo
uv run python -m labcloud arquitectura    # topología del sistema
uv run python -m labcloud servicio solicitudes --recargar   # un servicio solo
uv run python -m labcloud iniciar --solo gateway solicitudes resultados
```

---

## Qué se puede observar en el panel

| Página | Qué demuestra |
|---|---|
| **Panel de nodos** | Topología real: nodos, puertos, PID, hilos vivos y tráfico dirigido por el Gateway. |
| **Laboratorio de hilos** | Cambio de la cantidad de hilos en caliente, pruebas de carga y comparativa de 1, 2, 4 y 8 hilos con gráfica. |
| **Solicitudes** | Creación individual o simultánea; muestra qué hilo atendió cada solicitud y cuánto esperó en cola. |
| **Resultados** | Informes con sus valores y el hilo que los produjo. |
| **Eventos y notificaciones** | Observadores suscritos, traza de entregas y **simulación de caída** del servicio secundario. |
| **Clientes / Muestras** | Datos maestros y avance del estado de cada muestra. |

---

## Demostración automática

Con los servicios en ejecución:

```bash
cd backend
uv run python scripts/demostracion.py
```

Recorre los cinco escenarios que la actividad pide evidenciar y guarda un
informe en Markdown dentro de `backend/informes/`:

1. **Distribución en nodos** — procesos, puertos, PID e hilos de cada servicio.
2. **Flujo completo de una solicitud** — REST, hilo, evento y notificación.
3. **Procesamiento concurrente** — 5 solicitudes con 3 hilos: dos esperan en cola.
4. **Concurrencia y escalabilidad** — comparativa de 1, 2, 4 y 8 hilos.
5. **Tolerancia a fallos** — con el Servicio de Notificaciones caído, la
   solicitud se procesa igual y el evento se entrega al recuperarse.

### Resultado de la comparativa

24 solicitudes, análisis simulado de 0,25 s por muestra:

| Hilos | Tiempo total | Solicitudes/s | Espera en cola | Aceleración |
|---|---|---|---|---|
| 1 | 6,158 s | 3,90 | 2941 ms | x0,97 |
| 2 | 3,084 s | 7,78 | 1409 ms | x1,95 |
| 4 | 1,545 s | 15,53 | 644 ms | x3,88 |
| 8 | 0,779 s | 30,81 | 256 ms | x7,70 |

---

## Pruebas automatizadas

```bash
cd backend
uv run pytest -v
```

40 pruebas que verifican las propiedades que la arquitectura promete:

| Archivo | Qué comprueba |
|---|---|
| `tests/test_pool.py` | Que varias solicitudes se procesen a la vez, que las sobrantes esperen en cola y que el pool se redimensione sin perder tareas. |
| `tests/test_eventos.py` | Que publicar **no bloquee** al productor y que un observador caído no pierda el evento. |
| `tests/test_mediator.py` | Que los servicios no se llamen entre sí y que la coordinación siga el orden previsto. |
| `tests/test_gateway.py` | Que el enrutamiento resuelva el servicio correcto y que la escritura sin token se rechace en el Gateway. |
| `tests/test_servicios.py` | Contrato HTTP de cada servicio e identidad de su nodo. |

Revisión de estilo:

```bash
cd backend && uv run ruff check labcloud tests scripts
cd frontend && npx tsc --noEmit && npm run lint
```

---

## Documentación

| Documento | Contenido |
|---|---|
| [`docs/arquitectura.md`](docs/arquitectura.md) | Diseño detallado, trazabilidad de requerimientos y análisis de desempeño. |
| [`docs/diagramas/01-componentes.md`](docs/diagramas/01-componentes.md) | Figura 1 — Diagrama UML de componentes. |
| [`docs/diagramas/02-secuencia.md`](docs/diagramas/02-secuencia.md) | Figura 2 — Diagrama UML de secuencia del procesamiento concurrente. |
| [`docs/diagramas/03-despliegue.md`](docs/diagramas/03-despliegue.md) | Figura 3 — Diagrama UML de despliegue. |
| [`backend/README.md`](backend/README.md) | Referencia de la API y configuración del backend. |
| [`frontend/README.md`](frontend/README.md) | Estructura del panel de control. |

Los diagramas están escritos en Mermaid y GitHub los renderiza directamente.

---

## Configuración

Variables de entorno del backend (todas tienen valor por defecto):

| Variable | Por defecto | Para qué |
|---|---|---|
| `LABCLOUD_HILOS` | `4` | Hilos iniciales del pool de procesamiento. |
| `LABCLOUD_DURACION_ANALISIS` | `0.35` | Duración simulada de un análisis, en segundos. |
| `LABCLOUD_AUTH_MODO` | `escritura` | Política del Gateway: `escritura`, `siempre` o `nunca`. |
| `LABCLOUD_TIMEOUT` | `15.0` | Tiempo de espera entre servicios, en segundos. |
| `LABCLOUD_REINTENTOS` | `2` | Reintentos de una llamada REST fallida. |
| `LABCLOUD_DATA_DIR` | `backend/data` | Carpeta de las bases de datos. |
| `LABCLOUD_URL_<SERVICIO>` | — | Dirección de un servicio en otra máquina. |
| `PORT_<SERVICIO>` | Ver tabla de nodos | Puerto de un servicio. |

Ejemplo de despliegue en varias máquinas, sin cambiar una línea de código:

```bash
LABCLOUD_URL_RESULTADOS=http://10.0.0.5:8002 \
LABCLOUD_URL_NOTIFICACIONES=http://10.0.0.6:8003 \
uv run python -m labcloud iniciar --solo gateway solicitudes
```

---

## Enlaces del proyecto

* Repositorio: <https://github.com/JuanCruz21/Actividad4ArquitecturaDeSoftware>
* Video de presentación: *pendiente de publicar*
