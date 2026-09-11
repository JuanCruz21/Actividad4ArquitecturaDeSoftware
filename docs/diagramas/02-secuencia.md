# Figura 2. Diagrama UML de secuencia — procesamiento concurrente

Corresponde a la Figura 2 del documento. Representa la llegada simultánea de
tres solicitudes, su reparto entre los hilos del pool y la notificación
asíncrona posterior.

```mermaid
sequenceDiagram
    autonumber
    actor R as Recepcionista
    participant GW as API Gateway<br/>(Proxy)
    participant SOL as Servicio de Solicitudes<br/>(Mediator)
    participant P as Pool de hilos
    participant H1 as Hilo 1
    participant H2 as Hilo 2
    participant MUE as Servicio de Muestras
    participant RES as Servicio de Resultados<br/>(sujeto observable)
    participant NOT as Servicio de Notificaciones<br/>(observador)

    Note over R,GW: Llegan tres solicitudes casi al mismo tiempo
    R->>GW: POST /api/solicitudes (A, B, C)
    GW->>GW: Valida el token de acceso
    GW->>SOL: POST /solicitudes (reenvío)

    SOL->>SOL: Valida cliente y muestra
    SOL->>P: Encola A, B y C

    par Procesamiento concurrente
        P->>H1: Asigna la solicitud A
        H1->>MUE: PATCH estado = en_analisis
        H1->>H1: Ejecuta el análisis
        H1->>RES: POST /resultados (A)
    and
        P->>H2: Asigna la solicitud B
        H2->>MUE: PATCH estado = en_analisis
        H2->>H2: Ejecuta el análisis
        H2->>RES: POST /resultados (B)
    end

    Note over P: Con 2 hilos configurados,<br/>C espera en cola hasta que uno se libera
    P->>H1: Asigna la solicitud C al quedar libre

    RES-->>H1: 201 Created (resultado registrado)
    RES-->>H2: 201 Created (resultado registrado)

    Note over RES,NOT: Publicación asíncrona: el productor no espera
    RES--)NOT: evento resultado.disponible
    NOT->>NOT: Genera y simula el envío de la notificación

    H1-->>SOL: Resultado de A
    SOL-->>GW: 201 Created
    GW-->>R: Respuesta con el estado de la solicitud
```

## Lectura del diagrama

* El **bloque `par`** representa el procesamiento simultáneo: dos hilos avanzan
  al mismo tiempo sobre solicitudes distintas.
* La **nota sobre el pool** refleja la regla descrita en la sección 8.5.1 del
  diseño: las solicitudes que exceden la cantidad de hilos permanecen en cola.
* La **flecha punteada abierta** (`--)`) hacia Notificaciones indica un mensaje
  asíncrono: el Servicio de Resultados responde a quien lo llamó sin esperar a
  que la notificación se entregue. Si el observador estuviera caído, el flujo
  principal terminaría igual y el evento se archivaría para reintento.
