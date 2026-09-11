# Figura 3. Diagrama UML de despliegue

Corresponde a la Figura 3 del documento. Muestra cómo se distribuyen los
artefactos del sistema sobre los nodos de ejecución.

En el prototipo académico los nodos se simulan mediante procesos independientes
en puertos distintos del mismo equipo; en un entorno real cada nodo sería una
máquina virtual, un contenedor o un recurso de infraestructura en la nube.

```mermaid
graph TB
    subgraph disp["«dispositivo» Equipo del usuario"]
        NAV["«entorno de ejecución»<br/><b>Navegador</b><br/>———————<br/>Frontend Next.js<br/>:3000"]
    end

    subgraph host["«dispositivo» Servidor de aplicaciones (equipo de desarrollo)"]
        subgraph nodo1["«nodo de ejecución» Nodo 1 — Entrada y acceso"]
            P1["«proceso» uvicorn<br/><b>API Gateway</b> :8000"]
            P2["«proceso» uvicorn<br/><b>Servicio de Usuarios</b> :8004"]
            A1[("usuarios.db")]
        end

        subgraph nodo2["«nodo de ejecución» Nodo 2 — Procesamiento"]
            P3["«proceso» uvicorn<br/><b>Servicio de Solicitudes</b> :8001<br/>———————<br/>«hilos» pool configurable<br/>solicitud-worker_0 … _N"]
            A2[("solicitudes.db")]
        end

        subgraph nodo3["«nodo de ejecución» Nodo 3 — Servicios de soporte"]
            P4["«proceso» uvicorn<br/><b>Servicio de Resultados</b> :8002<br/>———————<br/>«hilos» despachadores de eventos"]
            P5["«proceso» uvicorn<br/><b>Servicio de Notificaciones</b> :8003"]
            A3[("resultados.db")]
            A4[("notificaciones.db")]
        end

        subgraph nodo4["«nodo de ejecución» Nodo 4 — Datos maestros"]
            P6["«proceso» uvicorn<br/><b>Servicio de Clientes</b> :8005"]
            P7["«proceso» uvicorn<br/><b>Servicio de Muestras</b> :8006"]
            A5[("clientes.db")]
            A6[("muestras.db")]
        end
    end

    NAV -->|"HTTPS / JSON"| P1
    P1 -->|"TCP :8004"| P2
    P1 -->|"TCP :8001"| P3
    P1 -->|"TCP :8002"| P4
    P1 -->|"TCP :8003"| P5
    P1 -->|"TCP :8005"| P6
    P1 -->|"TCP :8006"| P7

    P3 -->|"TCP :8005"| P6
    P3 -->|"TCP :8006"| P7
    P3 -->|"TCP :8002"| P4
    P4 -.->|"evento HTTP :8003"| P5

    P2 --- A1
    P3 --- A2
    P4 --- A3
    P5 --- A4
    P6 --- A5
    P7 --- A6
```

## Correspondencia con un despliegue real

| Elemento del prototipo | Equivalente en producción |
|---|---|
| Proceso `uvicorn` en un puerto | Contenedor o máquina virtual con su propia dirección de red |
| Nodo lógico | Grupo de instancias o *namespace* del orquestador |
| Archivo SQLite por servicio | Instancia de base de datos independiente por servicio |
| Evento HTTP directo | Bus de mensajería (RabbitMQ, Kafka, SNS/SQS) |
| Escalado: aumentar hilos del pool | Réplicas del Servicio de Solicitudes tras un balanceador |

El diseño permite ese tránsito sin cambiar el código: la ubicación de cada
servicio se resuelve mediante variables de entorno (`LABCLOUD_URL_<SERVICIO>`),
de modo que un servicio puede moverse a otra máquina sin tocar a los demás.
