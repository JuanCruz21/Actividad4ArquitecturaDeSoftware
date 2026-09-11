# Figura 1. Diagrama UML de componentes

Corresponde a la Figura 1 del documento de la actividad. Muestra los componentes
de LabCloud Distributed y las interfaces por las que se comunican: REST para las
operaciones que necesitan respuesta inmediata y eventos para las que pueden
ejecutarse de forma desacoplada.

```mermaid
graph TB
    UI["<b>Frontend Next.js</b><br/><i>«aplicación web»</i><br/>Panel de control · :3000"]

    subgraph n1["Nodo 1 — Entrada y acceso"]
        direction TB
        GW["<b>API Gateway</b><br/><i>«componente»</i> :8000<br/>Patrón Proxy"]
        USR["<b>Servicio de Usuarios</b><br/><i>«componente»</i> :8004"]
        BDU[("usuarios.db")]
        USR --- BDU
    end

    subgraph n2["Nodo 2 — Procesamiento"]
        direction TB
        SOL["<b>Servicio de Solicitudes</b><br/><i>«componente»</i> :8001<br/>Patrón Mediator"]
        POOL["<b>Pool de hilos</b><br/><i>«subsistema»</i><br/>N hilos configurables"]
        BDS[("solicitudes.db")]
        SOL --- POOL
        SOL --- BDS
    end

    subgraph n3["Nodo 3 — Servicios de soporte"]
        direction TB
        RES["<b>Servicio de Resultados</b><br/><i>«componente»</i> :8002<br/>Observer · sujeto"]
        NOT["<b>Servicio de Notificaciones</b><br/><i>«componente»</i> :8003<br/>Observer · observador"]
        BDR[("resultados.db")]
        BDN[("notificaciones.db")]
        RES --- BDR
        NOT --- BDN
        RES -.->|"evento<br/>resultado.disponible"| NOT
    end

    subgraph n4["Nodo 4 — Datos maestros"]
        direction TB
        CLI["<b>Servicio de Clientes</b><br/><i>«componente»</i> :8005"]
        MUE["<b>Servicio de Muestras</b><br/><i>«componente»</i> :8006"]
        BDC[("clientes.db")]
        BDM[("muestras.db")]
        CLI --- BDC
        MUE --- BDM
    end

    UI ==>|"HTTP/REST · único punto de entrada"| GW
    GW -->|REST| USR
    GW -->|REST| SOL
    GW -->|REST| RES
    GW -->|REST| NOT
    GW -->|REST| CLI
    GW -->|REST| MUE

    POOL -->|"REST · validar y actualizar"| MUE
    SOL -->|"REST · validar cliente"| CLI
    POOL -->|"REST · registrar resultado"| RES

    classDef comp fill:#0e1522,stroke:#38bdf8,color:#e7edf7
    classDef bd fill:#141d2e,stroke:#2b3c5c,color:#93a3bd
    class UI,GW,USR,SOL,POOL,RES,NOT,CLI,MUE comp
    class BDU,BDS,BDR,BDN,BDC,BDM bd
```

## Lectura del diagrama

| Elemento | Papel en la arquitectura |
|---|---|
| Frontend Next.js | Único consumidor externo. Solo conoce la dirección del Gateway. |
| API Gateway | Punto de entrada; valida el acceso y direcciona cada petición. |
| Servicio de Solicitudes | Concentra el procesamiento concurrente y coordina a los demás servicios. |
| Pool de hilos | Subsistema interno del proceso de Solicitudes; atiende varias solicitudes a la vez. |
| Servicio de Resultados | Registra el informe y emite el evento de disponibilidad. |
| Servicio de Notificaciones | Consume el evento y simula el envío al usuario. |
| Bases de datos | Una por servicio: ningún componente lee la base de otro. |

Las flechas continuas representan comunicación síncrona (REST/HTTP). La flecha
punteada representa comunicación asíncrona basada en eventos: el productor no
espera respuesta del consumidor.
