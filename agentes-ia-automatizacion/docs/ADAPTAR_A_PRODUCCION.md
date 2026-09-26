# Adaptar el proyecto a producción

Este demo corre **offline**: los agentes no llaman a ninguna API, las fallas se
sortean con `random` y la "base de datos" es un diccionario. Lo que **no** es
simulado es la arquitectura: la política de reintentos, el backoff exponencial
con jitter, el fallback, los puntos de control y el monitoreo son los mismos
que se necesitan contra herramientas reales.

La idea central es simple: **`agentes.py` es el único archivo que cambia**.
`manejo_errores.py`, `monitoreo.py` y el orquestador no se tocan.

---

## 1. Mapa agente simulado → herramienta real

| Agente (demo) | `ejecutar()` simulado | Herramienta real equivalente | Consideraciones |
|---|---|---|---|
| `AgenteValidarPago` | aprueba el cobro con un id falso | API de la pasarela (`POST /v1/pagos/{id}/confirmar`) | **Idempotencia**: la clave `pedido_id` debe volver en cada reintento, si no se cobran dos veces. Firma criptográfica del webhook antes de confiar en el estado. |
| `AgenteActualizarStock` | descuenta unidades en un dict | API del ERP/WMS (`POST /wms/inventario/descontar`) | Transacción + `reservation_id`; manejar concurrencia con versionado optimista (`If-Match` / `expected_version`). El error 409 (stock tomado) es **no reintentable**: dispara otro flujo, no backoff. |
| `AgentePrepararEnvio` | emite una guía ficticia | API del transportista (`POST /envios/guia`) | Correlación de webhooks: la respuesta final suele ser asíncrona → cola de eventos, no polling aggressive. |
| `AgenteNotificar` | "envía" un mensaje | API de mensajería (WhatsApp/SMS/email) o cola (SQS/Kafka) | Los proveedores devuelven 429 con `Retry-After`: el backoff debe respetarlo en lugar del propio. |
| `AgenteFallbackStock` | escribe en una planilla y abre un ticket | Google Sheets/Airtable + Jira/Zendesk, o cola de "revisión humana" | El fallback es un **camino de negocio**, no un consolation prize: tiene SLA, responsable y auditoría. |

### Cómo se ve un agente real

La clase base se conserva; sólo cambia el cuerpo de `ejecutar()` y desaparece
la simulación de fallas (esa parte la pasan a cumplir el timeout y los errores
reales):

```python
class AgenteValidarPago(Agente):
    def ejecutar(self, contexto: dict) -> dict:
        """Confirma el cobro en la pasarela de pagos."""
        try:
            respuesta = cliente_pagos.confirmar(
                pedido_id=contexto["pedido_id"],
                monto=contexto["monto"],
                idempotency_key=contexto["pedido_id"],  # clave de idempotencia
                timeout=2.0,                              # segundos, no milisegundos
            )
        except TimeoutError as exc:
            raise ErrorTimeoutAgente("TIMEOUT_PAGO", str(exc), herramienta="pasarela")
        except HTTPStatusError as exc:
            if exc.status_code in (402, 422):            # rechazo de negocio
                raise ErrorAgente(
                    "RECHAZO_NEGOCIO_PAGO", "el pago fue rechazado",
                    reintentable=False, herramienta="pasarela",
                )
            raise ErrorAgente(                           # 5xx / 429: reintentable
                "INDISPONIBLE_PAGO", f"HTTP {exc.status_code}",
                reintentable=True, herramienta="pasarela",
            )
        return {"accion": "confirmar_pago", "autorizacion": respuesta["id"], ...}
```

`prob_fallo`, `prob_rechazo` y `timeout_simulado_ms` se vuelven irrelevantes;
lo que queda del demo es la **clasificación del error** (reintentable vs. no
reintentable), que es la decisión más importante del diseño.

---

## 2. Dónde va cada pieza

| Concepto | Dónde vive hoy | En producción |
|---|---|---|
| Secuencia de pasos y política | `config.json` | Config del orquestador (YAML/JSON) o flags por entorno |
| Reintentos y backoff | `manejo_errores.reintentar` | Igual, con `jitter` real y límites por herramienta |
| Degradación | `manejo_errores.ejecutar_con_fallback` | Igual + cola de compensación |
| Puntos de control | `config.json` → `critico` | Igual: define si el fallo frena el pedido |
| Eventos | `monitoreo.registrar_evento` | OpenTelemetry / CloudWatch / Loki + alerta a Slack/PagerDuty |
| Estado del pedido | `contexto` en memoria | Base de datos / Redis, para poder retomar y auditar |
| Reporte y línea de tiempo | `orquestador.generar_reporte/diagrama` | Idem, más un tablero con SLOs |

---

## 3. Cambios mínimos para que funcione de verdad

1. **Idempotencia.** Todo paso que muta estado (cobrar, descontar stock) debe
   poder repetirse sin duplicar efectos. Es la condición para poder reintentar
   con confianza. Clave: `idempotency_key = pedido_id + paso`.
2. **Timeout real por herramienta.** `timeout_simulado_ms` → `timeout=2.0` en
   el cliente HTTP. Timeouts distintos por dependencia (una pasarela lenta no
   debe comerse el presupuesto del ERP).
3. **Circuit breaker.** El backoff por sí solo martilla un servicio caído. Sumar
   un breaker: si `max_reintentos` se agotan N veces seguidas, abrir el circuito
   y no llamar hasta `reset_timeout`. El fallback es la salida natural.
4. **Cola en vez de proceso bloqueante.** El orquestador encola el pedido
   (`SQS`/`Kafka`/`RabbitMQ`) y cada agente es un consumidor. Así un fallo de
   30 s no bloquea el proceso, y el reintento es un mensaje nuevo con
   `delay_seconds` (el backoff lo aplica la cola, gratis).
5. **Estado persistente.** Guardar `contexto` por paso permite reanudar desde
   el paso 3 si el proceso muere, y auditar qué agente corrió cuándo.
6. **Alertas de verdad.** Los eventos `WARNING`/`ERROR` del log son la fuente:
   `fallback_activado` → aviso al equipo de operaciones; `paso_fin` FALLIDO en
   un paso crítico → PagerDuty.
7. **Concurrencia.** `max_reintentos` × número de pedidos simultáneos define la
   carga: conviene un semaphore o rate limit por herramienta downstream.

---

## 4. Reutilizar el diseño en otras herramientas

La mecánica es idéntica para cualquier automatización, porque el wrapper no
depende del dominio:

| Escenario | `accion` | Fallback típico |
|---|---|---|
| Cargar un CSV a una API | `requests.post(...)` por fila | Cola de errores + planilla de pendientes |
| Procesar documentos con un LLM | llamada al modelo con timeout | Modelo chico / plantilla determinística / revisión humana |
| Sincronizar dos bases | query + `upsert` transaccional | Reintento con backoff + alerta de consistencia |
| Enviar emails masivos | API del proveedor | Cola + worker con rate limit |
| Orquestar tareas de un data pipeline | `run_job(...)` | Re-ejecutar el job desde el último checkpoint |

En todos los casos lo que se conserva es el contrato:

```python
resultado = ejecutar_con_fallback(
    accion,                              # cualquier cosa que pueda fallar
    nombre_paso="cargar_csv",
    paso_id=1,
    agente="AgenteCargarCSV",
    max_reintentos=3,                    # política por herramienta
    backoff_base=1.0,                    # espera base
    accion_fallback=escribir_en_cola,    # degradación
    nombre_fallback="AgenteColaErrores",
)
```

Y las tres preguntas que este proyecto responde de forma explícita:

1. **¿Cuánto insistir?** `max_reintentos` + backoff exponencial con jitter,
   distinguendo errores reintentables de los que no lo son.
2. **¿Qué hacer cuando ya no hay más intentos?** Un fallback con sentido de
   negocio (degradar en lugar de romper) y una alerta.
3. **¿Cómo me entero?** Un evento por intento, por backoff, por fallback y por
   cierre de paso, en JSONL, con `run_id` para comparar corridas.
