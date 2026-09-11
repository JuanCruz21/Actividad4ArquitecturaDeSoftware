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
| **Laboratorio de hilos** | Cambio de la cantidad de hilos en caliente, pruebas de carga y comparativa de 1 a 64 hilos con gráfica. |
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
4. **Concurrencia y escalabilidad** — comparativa de 1 a 64 hilos.
5. **Tolerancia a fallos** — con el Servicio de Notificaciones caído, la
   solicitud se procesa igual y el evento se entrega al recuperarse.

### Resultado de la comparativa

64 solicitudes por configuración, análisis simulado de 0,2 s por muestra
(procesamiento secuencial estimado: 12,8 s). Equipo de 8 núcleos lógicos.

**Modo pool aislado** — solo el análisis, sin llamadas a otros servicios.
Mide el comportamiento puro de la concurrencia:

| Hilos | Tiempo total | Solicitudes/s | Latencia media | Espera en cola | Aceleración | Eficiencia por hilo |
|---|---|---|---|---|---|---|
| 1 | 13,057 s | 4,90 | 6626 ms | 6422 ms | x0,98 | 0,98 |
| 2 | 6,632 s | 9,65 | 3415 ms | 3209 ms | x1,93 | 0,97 |
| 4 | 3,297 s | 19,41 | 1751 ms | 1545 ms | x3,88 | 0,97 |
| 8 | 1,665 s | 38,44 | 931 ms | 724 ms | x7,69 | 0,96 |
| 16 | 0,835 s | 76,67 | 515 ms | 309 ms | x15,33 | 0,96 |
| 32 | 0,420 s | 152,24 | 307 ms | 102 ms | x30,45 | 0,95 |
| 64 | 0,219 s | 291,76 | 205 ms | 0,1 ms | x58,35 | 0,91 |

**Modo flujo distribuido** — cada solicitud recorre el sistema completo a través
del Mediator (Muestras → Resultados → evento → Notificaciones):

| Hilos | Tiempo total | Solicitudes/s | Latencia media | Aceleración | Eficiencia por hilo |
|---|---|---|---|---|---|
| 1 | 13,910 s | 4,60 | 7016 ms | x0,92 | 0,92 |
| 2 | 6,939 s | 9,22 | 3576 ms | x1,84 | 0,92 |
| 4 | 3,478 s | 18,40 | 1856 ms | x3,68 | 0,92 |
| 8 | 1,749 s | 36,60 | 979 ms | x7,32 | 0,92 |
| 16 | 0,939 s | 68,16 | 579 ms | x13,63 | 0,85 |
| 32 | 0,547 s | 116,88 | 397 ms | x23,38 | 0,73 |
| 64 | 0,324 s | 197,39 | 271 ms | x39,48 | **0,62** |

### Lectura de los resultados

Mirar solo el tiempo total lleva a una conclusión equivocada: sigue bajando
hasta 64 hilos en ambos modos. La señal del **rendimiento decreciente** está en
la eficiencia por hilo.

* **Con el pool aislado la eficiencia apenas cae** (0,98 → 0,91). El análisis
  simulado espera sin ocupar el procesador —igual que una operación de entrada y
  salida o una llamada de red reales—, así que los hilos avanzan de verdad en
  paralelo aunque superen los 8 núcleos del equipo. La concurrencia por hilos es
  la herramienta adecuada para este tipo de trabajo.
* **Con el flujo distribuido la eficiencia se desploma** (0,92 → 0,62). A partir
  de 16 hilos, el cuello de botella deja de ser el pool y pasa a ser el
  **Servicio de Resultados**, que recibe 64 peticiones concurrentes. Duplicar de
  32 a 64 hilos solo multiplicó el throughput por 1,69 en lugar de por 2.

La conclusión práctica es que, pasados los 16 hilos, el camino para seguir
escalando no es agregar hilos al Nodo 2 sino **replicar el servicio saturado**,
que es exactamente lo que permite haber separado los componentes en procesos
independientes (RNF04).

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
| `LABCLOUD_TIMEOUT_PRUEBAS` | `900.0` | Tiempo de espera del Gateway para las rutas de pruebas de carga. |
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
