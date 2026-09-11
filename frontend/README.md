# Frontend — LabCloud Distributed

Panel de control del sistema distribuido, construido con **Next.js 16**
(App Router), TypeScript y Tailwind CSS 4.

```bash
npm install
cp .env.local.example .env.local
npm run dev
```

Abrir <http://localhost:3000>. Requiere el backend en ejecución
(`cd ../backend && uv run python -m labcloud iniciar`).

## El frontend solo conoce el Gateway

Todas las peticiones salen hacia `NEXT_PUBLIC_GATEWAY_URL`
(`http://127.0.0.1:8000` por defecto). El navegador nunca conoce los puertos de
los servicios internos: esa es, del lado del cliente, la propiedad que aporta el
patrón Proxy. Si un servicio se mueve de máquina, el frontend no cambia.

## Páginas

| Ruta | Qué muestra |
|---|---|
| `/` | **Panel de nodos.** Topología en vivo: nodos, servicios, puertos, PID, hilos y tráfico dirigido por el Gateway. |
| `/concurrencia` | **Laboratorio de hilos.** Ajuste del pool en caliente, pruebas de carga y comparativa de configuraciones con gráfica. |
| `/solicitudes` | Creación individual o simultánea de solicitudes; hilo asignado y espera en cola de cada una. |
| `/resultados` | Informes desplegables con sus valores y el hilo que los produjo. |
| `/notificaciones` | Observadores suscritos, traza de entregas y simulación de caída del servicio secundario. |
| `/clientes`, `/muestras` | Datos maestros del laboratorio. |
| `/login` | Acceso; el token se guarda en `localStorage` y viaja en cada petición. |

## Estructura

```
app/            Una carpeta por página (App Router)
components/
  Navegacion.tsx        Barra lateral con el estado del sistema
  Sesion.tsx            Contexto de autenticación
  Encabezado.tsx        Encabezado con el nodo al que pertenece la página
  GraficaComparativa.tsx  Gráfica SVG de la comparativa de hilos
  ui.tsx                Piezas reutilizadas: tarjetas, tablas, métricas, avisos
lib/
  api.ts        Cliente HTTP hacia el Gateway y manejo del token
  tipos.ts      Tipos del dominio, espejo de los esquemas del backend
```

## Verificación

```bash
npx tsc --noEmit
npm run lint
npm run build
```
