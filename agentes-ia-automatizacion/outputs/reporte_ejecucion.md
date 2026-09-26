# Reporte de ejecución — Procesamiento de pedido de frutería online

- **Estado del proceso**: **COMPLETADO_CON_ALERTAS**
- **Corrida**: `run-20260926-131358`
- **Fecha**: 2026-09-26T13:14:00-03:00
- **Pedido**: `PED-2026-0001` — María Gómez
- **Semilla**: `42` (corrida reproducible)
- **Política**: `max_reintentos=3`, `backoff_base=1.0`s, estrategia exponencial
- **Duración lógica**: 8.91 s (latencias y backoffs simulados)

## Estados por paso

| # | Paso | Agente | Estado | Intentos | Reintentos | Duración (s) | Detalle |
|---|---|---|---|---|---|---|---|
| 1 | `validar_pago` | `AgenteValidarPago` | **OK** | 2 intentos | 1 | 1.39 | pago de 8,450 ARS aprobado |
| 2 | `actualizar_stock` | `AgenteActualizarStock` | **FALLBACK** | 4 intentos | 2 | 3.62 | **fallback → AgenteFallbackStock** · stock descontado en planilla manual y ticket TK-717889 abierto para revisión humana antes del despacho |
| 3 | `preparar_envio` | `AgentePrepararEnvio` | **OK** | 1 intento | 0 | 0.28 | guía emitida con EnvíaYa (demora estimada 72 h) |
| 4 | `notificar_cliente` | `AgenteNotificar` | **FALLIDO** | 3 intentos | 2 | 3.62 | la herramienta respondió con error transitorio (503 / ECONNRESET simulado) |

## Árbol de ejecución

```text
pedido PED-2026-0001
├─ [1] validar_pago  (OK · 1.39s · 2 intentos)
│    ✗ intento 1: INDISPONIBLE_PAGO — la herramienta respondió con error transitorio (503 / ECONNRESET simulado) · espera 0.91s
│    ✓ intento 2: OK
├─ [2] actualizar_stock  (FALLBACK · 3.62s · 4 intentos)
│    ✗ intento 1: INDISPONIBLE_ERP — la herramienta respondió con error transitorio (503 / ECONNRESET simulado) · espera 0.81s
│    ✗ intento 2: INDISPONIBLE_ERP — la herramienta respondió con error transitorio (503 / ECONNRESET simulado) · espera 1.62s
│    ✗ intento 3: INDISPONIBLE_ERP — la herramienta respondió con error transitorio (503 / ECONNRESET simulado)
│    ⚠ FALLBACK → AgenteFallbackStock (El ERP no respondió tras agotar los reintentos: se descuenta el stock en la planilla de control manual y el pedido queda marcado para revisión humana antes del despacho.)
│      ✓ intento 1: OK
├─ [3] preparar_envio  (OK · 0.28s · 1 intento)
│    ✓ intento 1: OK
└─ [4] notificar_cliente  (FALLIDO · 3.62s · 3 intentos)
     ✗ intento 1: INDISPONIBLE_NOTIF — la herramienta respondió con error transitorio (503 / ECONNRESET simulado) · espera 1.10s
     ✗ intento 2: INDISPONIBLE_NOTIF — la herramienta respondió con error transitorio (503 / ECONNRESET simulado) · espera 1.89s
     ✗ intento 3: INDISPONIBLE_NOTIF — la herramienta respondió con error transitorio (503 / ECONNRESET simulado)
```

## Resumen de monitoreo

- **4** pasos con estado
- **10** intentos totales
- **4** reintentos
- **1** paso con fallback
- **1** paso fallido
- **27** eventos en el log de la corrida

### Alertas
- `WARNING` [paso 2] 'AgenteActualizarStock' agotó 3 intentos (INDISPONIBLE_ERP); se degrada a 'AgenteFallbackStock'
- `WARNING` [paso 2] paso 'actualizar_stock' degradado a AgenteFallbackStock (punto de control: El ERP no respondió tras agotar los reintentos: se descuenta el stock en la planilla de control manual y el pedido queda marcado para revisión humana antes del despacho.)
- `ERROR` [paso 4] paso 'notificar_cliente' falló (INDISPONIBLE_NOTIF) y no tiene fallback: el pedido sigue su curso pero requiere contacto manual con el cliente

## Mapa de reintentos y fallbacks

| Paso | Falla típica | Reintentos | Fallback |
|---|---|---|---|
| 1. validar_pago | pasarela caída / timeout del PSP | hasta 3 intentos (backoff 1.0s ×2.0) | — |
| 2. actualizar_stock | ERP sin respuesta o 503 | hasta 3 intentos (backoff 1.0s ×2.0) | `AgenteFallbackStock` (planilla manual + ticket) |
| 3. preparar_envio | transportista lento o domicilio inválido | hasta 3 intentos (backoff 1.0s ×2.0) | — |
| 4. notificar_cliente | proveedor de mensajería inestable | hasta 3 intentos (backoff 1.0s ×2.0) | — (se emite alerta y contacto manual) |

Log completo (append) en `outputs/log_ejecucion.jsonl`; diagrama en `outputs/diagrama_pasos.png`.
