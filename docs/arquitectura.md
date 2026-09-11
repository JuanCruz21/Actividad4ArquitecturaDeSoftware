# Arquitectura de LabCloud Distributed

Documento técnico del prototipo. Explica cómo se materializan en el código las
decisiones descritas en el documento de la Actividad 4, y sirve de guía para
localizar cada concepto dentro del repositorio.

---

## 1. Distribución en nodos, procesos e hilos

El diseño distingue cuatro conceptos que conviene no confundir. El prototipo los
implementa así:

| Concepto | Implementación en el prototipo | Dónde verlo |
|---|---|---|
| **Servicio** | Funcionalidad independiente con su propio contrato HTTP y su propia base de datos. | `backend/labcloud/services/` |
| **Proceso** | Un `uvicorn` por servicio, en un puerto distinto. | `backend/labcloud/runner.py` |
| **Hilo** | Unidad de ejecución dentro del proceso de Solicitudes. | `backend/labcloud/services/solicitudes/pool.py` |
| **Nodo** | Agrupación lógica de procesos; en producción sería una máquina o contenedor. | `backend/labcloud/shared/config.py` |

### Mapa de nodos

| Nodo | Servicios | Puerto | Responsabilidad |
|---|---|---|---|
| **Nodo 1** — Entrada y acceso | API Gateway | 8000 | Punto de entrada único; valida y direcciona. |
| | Servicio de Usuarios | 8004 | Autenticación, roles y permisos. |
| **Nodo 2** — Procesamiento | Servicio de Solicitudes | 8001 | Procesamiento concurrente y coordinación. |
| **Nodo 3** — Servicios de soporte | Servicio de Resultados | 8002 | Registro de resultados; publica eventos. |
| | Servicio de Notificaciones | 8003 | Consume eventos y notifica. |
| **Nodo 4** — Datos maestros | Servicio de Clientes | 8005 | Clientes del laboratorio. |
| | Servicio de Muestras | 8006 | Muestras recibidas y su estado. |

> El Nodo 4 no aparece en la tabla original del documento: allí Clientes y
> Muestras se mencionan entre los servicios del sistema pero sin nodo asignado.
> Se agrupan en un cuarto nodo porque comparten una misma naturaleza —datos
> maestros de consulta frecuente y baja escritura— y así pueden escalarse con un
> criterio distinto al del nodo de procesamiento.

La ubicación de cada servicio se resuelve en `url_de()`, que admite una variable
de entorno por servicio. Mover un servicio a otra máquina no requiere tocar el
código de los demás:

```bash
LABCLOUD_URL_RESULTADOS=http://10.0.0.5:8002 uv run python -m labcloud iniciar
```

### Base de datos por servicio

Cada servicio posee su propio archivo SQLite en `backend/data/` y **ningún
servicio consulta las tablas de otro**. Las referencias entre servicios son
identificadores opacos (por ejemplo, `muestras.cliente_id`) que se resuelven
mediante una llamada REST, no mediante una llave foránea.

Esta separación es la que hace real la independencia de los servicios: sin ella,
la base de datos compartida volvería a acoplar lo que la arquitectura separó.

SQLite se abre en modo WAL y con `check_same_thread=False` porque varios hilos
del pool escriben simultáneamente (`backend/labcloud/shared/db.py`).

---

## 2. Comunicación

### 2.1 Síncrona (REST/HTTP)

Se usa cuando quien llama necesita la respuesta para continuar.

```
Frontend → API Gateway → Servicio interno → respuesta
```

* El Gateway usa `httpx.AsyncClient`: atiende muchas peticiones concurrentes sin
  bloquear su bucle de eventos (`backend/labcloud/gateway/proxy.py`).
* El Mediator usa `httpx.Client` síncrono: cada hilo del pool bloquea en su
  propia llamada, que es exactamente el comportamiento deseado
  (`backend/labcloud/shared/http_client.py`).
* Ambos aplican tiempo de espera y reintentos con retroceso, y registran la
  latencia de cada salto.

### 2.2 Asíncrona (eventos)

Se usa cuando el productor no debe esperar al consumidor.

```
Servicio de Resultados  ──publica──►  cola interna  ──hilos despachadores──►  observadores
```

`PublicadorEventos.publicar()` deja el evento en una cola y **regresa de
inmediato**; la entrega ocurre en hilos despachadores en segundo plano, con
hasta cuatro intentos y retroceso exponencial. Un evento que no se puede
entregar se archiva y puede reintentarse después
(`backend/labcloud/shared/events.py`).

### 2.3 Concurrencia (hilos)

Dentro del Servicio de Solicitudes, un `ThreadPoolExecutor` de tamaño
configurable procesa las solicitudes. El tamaño se cambia en caliente mediante
`PUT /api/concurrencia`.

---

## 3. Patrones de diseño

### 3.1 Proxy — `backend/labcloud/gateway/`

Cada servicio interno tiene un **representante** (`ProxyServicio`) dentro del
proceso del Gateway. El cliente conversa con el representante, que decide si la
petición procede y la reenvía.

Lo que aporta el intermediario, verificable en el prototipo:

| Aporte | Cómo comprobarlo |
|---|---|
| El cliente no conoce los servicios internos | El frontend solo usa `NEXT_PUBLIC_GATEWAY_URL`. |
| Control de acceso previo | `POST /api/clientes` sin token responde 401 sin tocar el servicio. |
| Medición por servicio | `GET /metricas` devuelve peticiones, errores y latencia por servicio. |
| Degradación controlada | Si un servicio cae, el Gateway responde 503 con el nombre del servicio y una sugerencia, no un error de conexión. |

La política de acceso se configura con `LABCLOUD_AUTH_MODO`:
`escritura` (por defecto: token obligatorio en POST/PUT/PATCH/DELETE),
`siempre` o `nunca`.

### 3.2 Mediator — `backend/labcloud/services/solicitudes/mediator.py`

En el flujo de una solicitud intervienen Clientes, Muestras y Resultados. Sin
mediador, cada servicio tendría que conocer y llamar a los demás.

```
Clientes ─┐
Muestras ─┼─► MediadorAnalisis ─► Resultados ─(evento)─► Notificaciones
Solicitud ┘
```

`MediadorAnalisis` es el único componente que conoce a todos los participantes
(sus *colegas*) y el orden de los pasos:

1. Marca la muestra como `en_analisis`.
2. Ejecuta el análisis en el hilo actual.
3. Registra el resultado, lo que dispara el evento.
4. Marca la muestra como `procesada`.

Incorporar un nuevo participante al flujo implica modificar solo esta clase.
Además, el mediador distingue entre pasos críticos y secundarios: si el Servicio
de Muestras no responde, el análisis continúa; si el de Resultados no responde,
la solicitud se marca como fallida y puede reprocesarse.

### 3.3 Observer distribuido — `backend/labcloud/shared/events.py`

* **Sujeto**: Servicio de Resultados. Mantiene el registro de observadores y
  publica `resultado.disponible`.
* **Observador**: Servicio de Notificaciones. Se suscribe al arrancar indicando
  una URL de callback, y recibe los eventos por HTTP.

El productor nunca conoce la lógica del consumidor: solo su URL. Agregar un
segundo observador (una auditoría, un servicio de mensajería) no requiere
modificar el Servicio de Resultados, basta con registrar otra suscripción en
`POST /api/eventos/suscripciones`.

El observador es **idempotente**: si el publicador reintenta una entrega ya
procesada, la notificación no se duplica.

---

## 4. Trazabilidad de requerimientos

### Requerimientos funcionales

| Código | Requerimiento | Implementación | Verificación |
|---|---|---|---|
| RF01 | Recibir solicitudes por el API Gateway | `gateway/main.py` → `reenviar()` | `tests/test_gateway.py` |
| RF02 | Crear y consultar solicitudes | `services/solicitudes/main.py` | Página *Solicitudes* |
| RF03 | Procesar varias solicitudes concurrentemente | `solicitudes/pool.py` | `tests/test_pool.py` |
| RF04 | Consultar el estado de una solicitud | `GET /api/solicitudes/{id}` | Página *Solicitudes* |
| RF05 | Registrar y consultar resultados | `services/resultados/main.py` | `tests/test_servicios.py` |
| RF06 | Comunicar los servicios mediante interfaces definidas | `shared/http_client.py`, `gateway/routing.py` | `GET /arquitectura` |
| RF07 | Generar un evento al haber resultado disponible | `resultados/main.py` → `publicador.publicar()` | `tests/test_eventos.py` |
| RF08 | Recibir el evento y simular la notificación | `services/notificaciones/main.py` | Página *Eventos y notificaciones* |
| RF09 | Probar con distintas cantidades de solicitudes e hilos | `solicitudes/bench.py` | Página *Laboratorio de hilos* |
| RF10 | Registrar la información de las pruebas | Tabla `pruebas_carga` | `GET /api/pruebas` |

### Requerimientos no funcionales

| Código | Requerimiento | Cómo se cumple |
|---|---|---|
| RNF01 | Procesamiento concurrente | Pool de hilos con cola; medición de concurrencia real alcanzada. |
| RNF02 | Bajo acoplamiento | Base de datos por servicio; eventos en lugar de llamadas directas. |
| RNF03 | Comunicación controlada | Cliente HTTP único con tiempos de espera, reintentos y trazas. |
| RNF04 | Escalar un servicio de forma independiente | Cada servicio es un proceso propio; el pool se redimensiona sin reiniciar. |
| RNF05 | Identificar tiempos y cuellos de botella | Métricas por tarea, por servicio y por corrida de prueba. |
| RNF06 | Estabilidad ante aumento de carga | Cola acotada por el pool; comparativa de configuraciones. |
| RNF07 | Un fallo secundario no detiene el flujo principal | Publicación asíncrona + archivo de eventos no entregados. |
| RNF08 | Facilidad de mantenimiento | Núcleo compartido, servicios uniformes y responsabilidades separadas. |

---

## 5. Evaluación del desempeño

El script `backend/scripts/demostracion.py` ejecuta los cinco escenarios de
evidencia y guarda un informe en `backend/informes/`.

### Resultado observado

Medición con **64 solicitudes por configuración** y un análisis simulado de
0,2 s por muestra, en un equipo de 8 núcleos lógicos. El procesamiento
estrictamente secuencial tomaría 12,8 s.

La comparativa se ejecuta en dos modos, y la diferencia entre ambos es la parte
interesante del resultado.

#### Modo *pool aislado*

Cada tarea ejecuta únicamente el análisis. Aísla el comportamiento de la
concurrencia, sin el costo de la red ni de los servicios remotos.

| Hilos | Tiempo total | Solicitudes/s | Latencia media | Espera en cola | Aceleración | Eficiencia por hilo |
|---|---|---|---|---|---|---|
| 1 | 13,057 s | 4,90 | 6626 ms | 6422 ms | x0,98 | 0,98 |
| 2 | 6,632 s | 9,65 | 3415 ms | 3209 ms | x1,93 | 0,97 |
| 4 | 3,297 s | 19,41 | 1751 ms | 1545 ms | x3,88 | 0,97 |
| 8 | 1,665 s | 38,44 | 931 ms | 724 ms | x7,69 | 0,96 |
| 16 | 0,835 s | 76,67 | 515 ms | 309 ms | x15,33 | 0,96 |
| 32 | 0,420 s | 152,24 | 307 ms | 102 ms | x30,45 | 0,95 |
| 64 | 0,219 s | 291,76 | 205 ms | 0,1 ms | x58,35 | 0,91 |

#### Modo *flujo distribuido completo*

Cada tarea recorre el sistema real: el Mediator actualiza la muestra, registra
el resultado en el Servicio de Resultados y este publica el evento.

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

**El tiempo total no basta para detectar la saturación.** En los dos modos el
tiempo sigue bajando hasta 64 hilos, así que quien mire solo esa columna
concluiría que conviene seguir añadiendo hilos indefinidamente. La señal real
está en la **eficiencia por hilo** —la aceleración obtenida dividida entre la
cantidad de hilos—, que mide cuánto aporta cada hilo adicional.

**1. Con el pool aislado la eficiencia apenas cae (0,98 → 0,91).** El resultado
puede sorprender, porque 64 hilos superan con creces los 8 núcleos del equipo.
La explicación es que el análisis simulado espera con `time.sleep`, que libera
el GIL: los hilos no compiten por el procesador, esperan en paralelo. Es
exactamente el comportamiento de una operación de entrada y salida o de una
llamada de red, que es el tipo de trabajo predominante en este sistema. La
conclusión es que **la concurrencia por hilos es la herramienta correcta para
esta carga**, y que la cantidad de núcleos no es el límite.

**2. Con el flujo distribuido la eficiencia se desploma (0,92 → 0,62).** Aquí
cada tarea sí sale a la red. Hasta 8 hilos la eficiencia se mantiene en 0,92;
a partir de 16 empieza a caer y en 64 cada hilo aporta apenas el 62 % de lo que
aportaba el primero. Duplicar de 32 a 64 hilos multiplicó el throughput por
1,69 en lugar de por 2.

**3. Dónde está el cuello de botella.** La diferencia entre ambas tablas lo
localiza sin ambigüedad: no está en el pool —que en modo aislado escala casi
perfecto con la misma cantidad de hilos— sino **aguas abajo**, en el Servicio de
Resultados, que con 64 hilos recibe 64 peticiones concurrentes y debe además
persistir cada resultado y encolar su evento.

**Consecuencia para la arquitectura.** Pasados los 16 hilos, la vía para seguir
escalando no es agrandar el pool del Nodo 2, sino **replicar el servicio
saturado**. Esa es precisamente la capacidad que da haber separado los
componentes en procesos independientes (RNF04): se puede aumentar la capacidad
del Servicio de Resultados sin tocar el resto del sistema. Un aumento
indiscriminado de hilos en el nodo de procesamiento, en cambio, solo traslada la
congestión y consume memoria.

Ambas comparativas se reproducen desde la página *Laboratorio de hilos* o con
`uv run python scripts/demostracion.py`, y quedan registradas en la tabla
`pruebas_carga` para comparar el comportamiento antes y después de un ajuste.

### Cuellos de botella identificados

| Punto | Observación | Mitigación aplicada o propuesta |
|---|---|---|
| Pool de Solicitudes | Con pocos hilos la espera en cola domina la latencia (6,4 s con un solo hilo). Deja de ser el límite a partir de 16 hilos. | Tamaño configurable en caliente. |
| Servicio de Resultados | Es el verdadero cuello de botella bajo carga alta: la eficiencia por hilo cae a 0,62 con 64 hilos concurrentes. | Réplicas del servicio tras un balanceador; es un proceso independiente, así que se escala solo. |
| API Gateway | Único punto de entrada: concentra todo el tráfico. | Cliente asíncrono y métricas por servicio; tiempo de espera propio para las rutas de pruebas; en producción, varias instancias tras un balanceador. |
| Escritura en SQLite | Una sola escritura a la vez por base. | Modo WAL, transacciones cortas y una base por servicio. En producción, un motor cliente-servidor. |
| Entrega de eventos | Un observador lento retrasaría al productor si la entrega fuera síncrona. | Publicación en cola con hilos despachadores; el productor nunca espera. |

---

## 6. Mapa del código

```
backend/labcloud/
├── shared/              Núcleo común a todos los servicios
│   ├── config.py        Registro de nodos, servicios y puertos
│   ├── db.py            Base de datos por servicio (SQLite + WAL)
│   ├── events.py        Observer distribuido: publicador y entrega
│   ├── http_client.py   Comunicación REST entre servicios
│   ├── logging_conf.py  Trazas con nodo, proceso e hilo
│   ├── security.py      Emisión y validación de tokens
│   └── service.py       Fábrica de aplicaciones FastAPI
├── gateway/             Patrón Proxy
│   ├── proxy.py         Representante local de cada servicio
│   ├── routing.py       Tabla de enrutamiento
│   └── main.py          Reenvío, control de acceso, /arquitectura y /salud
├── services/
│   ├── usuarios/        Autenticación (Nodo 1)
│   ├── solicitudes/     Nodo 2
│   │   ├── pool.py      Pool de hilos configurable
│   │   ├── mediator.py  Patrón Mediator
│   │   ├── analisis.py  Simulación del trabajo de laboratorio
│   │   └── bench.py     Pruebas de carga y comparativas
│   ├── resultados/      Sujeto observable (Nodo 3)
│   ├── notificaciones/  Observador (Nodo 3)
│   ├── clientes/        Datos maestros (Nodo 4)
│   └── muestras/        Datos maestros (Nodo 4)
└── runner.py            Orquestador de procesos
```
