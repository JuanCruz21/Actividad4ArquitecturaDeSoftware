# Backend — LabCloud Distributed

Siete servicios FastAPI que se ejecutan como procesos independientes. Gestión de
dependencias con **uv**; persistencia en **SQLite**, con una base de datos por
servicio.

```bash
uv sync
uv run python -m labcloud iniciar
```

## Orquestador

| Comando | Qué hace |
|---|---|
| `uv run python -m labcloud iniciar` | Levanta los siete servicios con trazas unificadas. |
| `uv run python -m labcloud iniciar --solo gateway solicitudes` | Levanta solo los servicios indicados. |
| `uv run python -m labcloud iniciar --recargar` | Recarga automática al editar el código. |
| `uv run python -m labcloud servicio resultados` | Un único servicio en primer plano. |
| `uv run python -m labcloud estado` | Consulta `/health` de cada nodo. |
| `uv run python -m labcloud arquitectura` | Imprime la topología del sistema. |

Cada servicio publica su documentación interactiva en `/docs`; la del Gateway,
en <http://127.0.0.1:8000/docs>.

## API a través del Gateway

Todo el tráfico externo entra por `http://127.0.0.1:8000`. El Gateway traduce
cada ruta pública a la ruta interna del servicio correspondiente.

### Arquitectura y estado

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/arquitectura` | Nodos, servicios, puertos, patrones y tabla de rutas. |
| `GET` | `/salud` | Estado de todos los nodos, consultado en paralelo. |
| `GET` | `/metricas` | Peticiones, errores y latencia medidos por servicio. |

### Autenticación — Servicio de Usuarios

| Método | Ruta | Descripción |
|---|---|---|
| `POST` | `/api/auth/login` | Emite el token de acceso. Ruta pública. |
| `POST` | `/api/auth/verificar` | Valida un token. |
| `GET` `POST` | `/api/usuarios` | Listado y registro de usuarios. |

### Operación del laboratorio

| Método | Ruta | Descripción |
|---|---|---|
| `GET` `POST` | `/api/clientes` | Clientes del laboratorio. |
| `GET` `POST` | `/api/muestras` | Muestras recibidas. |
| `PATCH` | `/api/muestras/{id}/estado` | Cambia el estado de una muestra. |
| `POST` | `/api/solicitudes` | Crea una solicitud y la envía al pool de hilos. |
| `GET` | `/api/solicitudes` | Listado, con filtros por estado y cliente. |
| `GET` | `/api/solicitudes/resumen` | Totales, promedios y reparto por hilo. |
| `POST` | `/api/solicitudes/{id}/reprocesar` | Reintenta una solicitud fallida. |
| `GET` | `/api/resultados` | Resultados registrados. |
| `GET` | `/api/notificaciones` | Notificaciones generadas a partir de eventos. |

`POST /api/solicitudes` acepta `esperar_resultado`: con `true` (por defecto)
responde 201 cuando el análisis termina; con `false` responde 202 de inmediato y
el hilo continúa en segundo plano.

### Concurrencia y pruebas

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/api/concurrencia` | Estado del pool, del mediador y de los hilos del proceso. |
| `PUT` | `/api/concurrencia` | Cambia la cantidad de hilos sin reiniciar el servicio. |
| `GET` | `/api/concurrencia/mediciones` | Detalle por tarea: hilo, espera en cola y procesamiento. |
| `POST` | `/api/pruebas/carga` | Lanza N solicitudes con una configuración de hilos. |
| `POST` | `/api/pruebas/comparativa` | Repite la carga con varias configuraciones (por defecto 1 a 64 hilos). |
| `GET` | `/api/pruebas` | Historial persistente de las corridas. |

### Observer distribuido

| Método | Ruta | Descripción |
|---|---|---|
| `GET` `POST` | `/api/eventos/suscripciones` | Observadores registrados. |
| `DELETE` | `/api/eventos/suscripciones/{id}` | Da de baja un observador. |
| `GET` | `/api/eventos/estado` | Cola, publicados, archivados y observadores. |
| `GET` | `/api/eventos/entregas` | Traza de cada intento de entrega. |
| `POST` | `/api/eventos/reintentar` | Reencola los eventos archivados. |
| `PUT` | `/api/simulacion/disponibilidad` | Simula la caída o recuperación del observador. |

## Ejemplos

```bash
# Token de acceso
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"admin@labcloud.co","clave":"admin123"}' | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

# Cambiar la cantidad de hilos del pool
curl -X PUT http://127.0.0.1:8000/api/concurrencia \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"hilos": 8}'

# Comparar de 1 a 64 hilos con 64 solicitudes (valores por defecto)
curl -X POST http://127.0.0.1:8000/api/pruebas/comparativa \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"solicitudes":64,"configuraciones":[1,2,4,8,16,32,64],"duracion_analisis_s":0.2,"aislar_pool":true}'

# La misma comparativa recorriendo el sistema distribuido completo
curl -X POST http://127.0.0.1:8000/api/pruebas/comparativa \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"solicitudes":64,"configuraciones":[1,2,4,8,16,32,64],"duracion_analisis_s":0.2,"aislar_pool":false}'

# Simular la caída del Servicio de Notificaciones
curl -X PUT http://127.0.0.1:8000/api/simulacion/disponibilidad \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"disponible": false}'
```

## Pruebas

```bash
uv run pytest -v          # 40 pruebas
uv run ruff check labcloud tests scripts
```

Las pruebas usan un directorio de datos temporal, de modo que no tocan las bases
de datos del prototipo.

## Estructura

```
labcloud/
├── shared/      Núcleo común: configuración, base de datos, eventos, HTTP, seguridad
├── gateway/     API Gateway (patrón Proxy)
├── services/    Un paquete por servicio
└── runner.py    Orquestador de procesos
data/            Bases SQLite, una por servicio (no se versiona)
informes/        Evidencias generadas por scripts/demostracion.py
scripts/         Demostración guiada del prototipo
tests/           Pruebas automatizadas
```

La documentación de diseño está en [`../docs/arquitectura.md`](../docs/arquitectura.md).
