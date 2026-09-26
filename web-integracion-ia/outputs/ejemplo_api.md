# Ejemplo de respuestas reales del API — CasaMuebles

Capturas de la API funcionando, obtenidas con `Invoke-WebRequest` / `urllib`
contra `http://127.0.0.1:8013` (uvicorn). Todos los bloques son la **respuesta
real**, no ejemplos inventados.

Servidor de referencia:

```bash
uvicorn app:app --port 8013
```

---

## 1. Consulta relevante al FAQ — envíos

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8013/api/chat" `
  -Method Post -ContentType "application/json" `
  -Body '{"message":"Hacen envios a todo el pais?"}'
```

**HTTP 200**

```json
{
  "respuesta": "Si, enviamos a todo el pais. El envio es gratis en compras superiores a $150.000 y tarda de 3 a 8 dias habiles segun la provincia. Los envios a domicilio incluyen subida a planta y coordinacion previa por WhatsApp.",
  "confianza": 0.759,
  "relevante": true,
  "pregunta_match": "Hacen envios a todo el pais?"
}
```

La consulta no usa las palabras exactas del FAQ en todos los términos
(`todo` y `a` son stopwords), pero el retrieval colapsa las 3 raíces
concordantes y supera el umbral de 0.30.

---

## 2. Consulta relevante al FAQ — devoluciones (lenguaje colloquial)

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8013/api/chat" `
  -Method Post -ContentType "application/json" `
  -Body '{"message":"quiero devolver un sillon"}'
```

**HTTP 200**

```json
{
  "respuesta": "Tenes 30 dias calendario desde la entrega para devolver un producto sin uso y en su packaging original. La devolucion es gratuita y te emitimos el reembolso en un maximo de 10 dias habiles una vez recibido el producto en nuestro centro de distribucion.",
  "confianza": 0.7,
  "relevante": true,
  "pregunta_match": "Como funcionan las devoluciones?"
}
```

Nótese que el usuario escribió `sillon` y el FAQ `devoluciones`; la raíz común
`devolv` + el sustantivo `sillon` en los keywords bastan para el match.

---

## 3. Consulta fuera de tema — guardrail activado

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8013/api/chat" `
  -Method Post -ContentType "application/json" `
  -Body '{"message":"como armo una pizza"}'
```

**HTTP 200**

```json
{
  "respuesta": "Perdon, todavia no tengo informacion sobre eso. Como soy el asistente de CasaMuebles, lo mejor es consultarme por envios, garantia, materiales, devoluciones, formas de pago o armado de muebles. Si preferis hablar con una persona, podes usar el formulario de contacto de esta pagina.",
  "confianza": 0.0,
  "relevante": false,
  "pregunta_match": null
}
```

El guardrail no es un error HTTP: la API responde 200 con
`relevante: false`, confianza baja y una respuesta amable que **reorienta al
usuario** hacia los temas que sí cubre el asistente. En el frontend la burbuja
se muestra con el metadato *"Sin coincidencia en el FAQ · tema fuera de alcance"*.

Otros casos fuera de tema verificados (todos `relevante: false`):

| Consulta | Confianza |
|---|---|
| `como armo una pizza` | 0.0 |
| `quien gano el mundial` | 0.0 |
| `clima de mañana` | 0.0 |
| `recomendame una receta de milanesas` | 0.073 |
| `cuanto esta el dolar` | 0.153 |

El último es el caso interesante: comparte la raíz `cuant` con *"Cuánto cuesta el
envío?"*, pero como es el **único** término en común se aplica la penalidad por
match único y el score cae de **0.340 → 0.153**, por debajo del umbral de 0.30.

---

## 4. Contacto guardado en SQLite

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8013/api/contacto" `
  -Method Post -ContentType "application/json" `
  -Body '{"nombre":"Mariana Gomez","email":"mariana.gomez@ejemplo.com","mensaje":"Quisiera saber si el placard a medida entra en un departamento de 2 ambientes.","categoria":""}'
```

**HTTP 201 Created**

```json
{
  "ok": true,
  "id": 3,
  "mensaje": "Consulta recibida. Te contactamos dentro de las 48 horas habiles."
}
```

Verificación en la base (`data/mensajes.db`, tabla `mensajes`):

```
$ python -c "import sqlite3; [print(r) for r in sqlite3.connect('data/mensajes.db').execute('SELECT * FROM mensajes')]"
(1, 'Mariana Gomez', 'mariana.gomez@ejemplo.com', 'Quisiera saber si el placard a medida entra en un departamento de 2 ambientes.', '2026-09-26T14:30:00+00:00')
(2, 'Diego Fernandez', 'diego.fernandez@ejemplo.com', 'Consulta por stock: necesito 2 comedores en 12 cuotas sin interes para un local comercial.', '2026-09-26T14:42:00+00:00')
```

---

## 5. Validaciones del formulario

**Email inválido → HTTP 422**

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8013/api/contacto" -Method Post -ContentType "application/json" `
  -Body '{"nombre":"Carlos Ruiz","email":"carlos.ruiz@","mensaje":"Necesito cotizacion para un comedor de 6 lugares.","categoria":""}'
```

```json
{
  "detail": "El email no tiene un formato valido."
}
```

**Mensaje demasiado corto → HTTP 422 (validación de Pydantic)**

```json
{
  "detail": [
    {
      "type": "string_too_short",
      "loc": ["body", "mensaje"],
      "msg": "String should have at least 10 characters",
      "input": "hola",
      "ctx": { "min_length": 10 }
    }
  ]
}
```

**Spam (campo trampa `categoria` relleno) → HTTP 200 pero `id: null`**

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8013/api/contacto" -Method Post -ContentType "application/json" `
  -Body '{"nombre":"Bot Spammer","email":"spam@ejemplo.com","mensaje":"COMPRA BARATA SEGUROS !!! http://spam.example","categoria":" electrodomesticos "}'
```

```json
{
  "ok": true,
  "id": null,
  "mensaje": "Consulta recibida. Te contactamos dentro de las 48 horas habiles."
}
```

El bot recibe una respuesta idéntica a la de un usuario legítimo (para no
revelar el filtro) pero **no se escribe nada en la base** — verificado: la tabla
quedó con las 2 filas de ejemplo, sin el mensaje de spam.

---

## 6. Health check y listado de contactos

```json
GET /api/salud     -> 200  {"estado": "ok", "empresa": "CasaMuebles", "preguntas_cargadas": 12}

GET /api/mensajes  -> 200  {
  "total": 2,
  "mensajes": [
    {
      "id": 1,
      "nombre": "Mariana Gomez",
      "email": "mariana.gomez@ejemplo.com",
      "mensaje": "Quisiera saber si el placard a medida entra en un departamento de 2 ambientes.",
      "creado_en": "2026-09-26T14:30:00+00:00"
    },
    {
      "id": 2,
      "nombre": "Diego Fernandez",
      "email": "diego.fernandez@ejemplo.com",
      "mensaje": "Consulta por stock: necesito 2 comedores en 12 cuotas sin interes para un local comercial.",
      "creado_en": "2026-09-26T14:42:00+00:00"
    }
  ]
}
```

Documentación interactiva de la API disponible en `/docs` (Swagger UI) y
`/redoc`, generadas automáticamente por FastAPI.
