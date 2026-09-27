# CasaMuebles — Web con Integración de IA

Sitio web funcional para una tienda online de muebles ficticia (**CasaMuebles**)
con **backend FastAPI** y **frontend estático responsive** que integra un
**asistente de chat** basado en recuperación sobre una base de conocimiento de
FAQs locales.

Punto clave: el chat **no depende de ningún LLM ni de servicios externos de IA**.
La recuperación es *textual* y está implementada con **solo biblioteca estándar
de Python** (`re`, `json`, `unicodedata`, `difflib`), por lo que el deploy es
mínimo (2 dependencias) y el costo de inferencia es **cero**.

## Problema

Una tienda online de muebles recibe decenas de consultas repetitivas todos los
días (*"¿hacen envíos a todo el país?"*, *"¿cuánto cuesta el envío?"*, *"¿aceptan
transferencia?"*). Responderlas a mano por chat o correo consume tiempo de
atención al cliente y, en temporada de promos, se pierde cobertura.

El riesgo típico de un chatbot de tienda es **responder cualquier cosa**: si el
motor no tiene un criterio claro de "no sé de esto", termina inventando
respuestas sobre productos, plazos o precios equivocados — y eso se traduce
directamente en reclamos y ventas perdidas.

Este proyecto resuelve ambas cosas:

1. **Automatizar las consultas frecuentes** con respuestas consistentes.
2. **Nunca improvisar**: cuando la consulta no pertenece al FAQ, el asistente
   responde con un mensaje amable que reorienta al usuario hacia los temas que sí
   cubre, sin inventar nada.

## Datos (FAQ)

- `data/faq.json` — **12 pares** `pregunta` / `respuesta` en español, escritos a
  mano para representar los temas reales de una tienda de muebles.
- Temas cubiertos: envíos y costos, garantía, materiales, devoluciones, formas
  de pago, armado de muebles, colores y tapizados, muebles a medida, rastreo de
  pedidos, showroom y cuidado/limpieza.
- Cada entrada tiene un campo opcional **`keywords`** con sinónimos y vocabulario
  coloquial que el cliente usaría en el chat pero que **no** aparece en la
  pregunta oficial. Esto es lo que permite que *"quiero devolver un sillón"* y
  *"devoluciones"* lleguen a la misma respuesta.
- Formato:

```json
{
  "pregunta": "Hacen envios a todo el pais?",
  "respuesta": "Si, enviamos a todo el pais. El envio es gratis en compras superiores a $150.000...",
  "keywords": ["envio", "enviar", "entrega", "llegar", "pais", "gratis", "reparto"]
}
```

## Proceso

### 1. API — FastAPI (`app.py`)

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Landing page (hero + chat + contacto) |
| `GET` | `/docs`, `/redoc` | Documentación interactiva autogenerada |
| `GET` | `/api/salud` | Health check |
| `GET` | `/api/faq` | Lista de preguntas (alimenta los chips de sugerencia del chat) |
| `POST` | `/api/chat` | Asistente de FAQ → `{respuesta, confianza, relevante, pregunta_match}` |
| `POST` | `/api/contacto` | Valida y persiste en SQLite → `201 {ok, id, mensaje}` |
| `GET` | `/api/mensajes` | Lista los contactos guardados (verificación de la demo) |

- Los modelos de entrada se validan con **Pydantic** (longitudes mínimas/máximas).
- El email se valida además con una **regex** explícita.
- Todas las rutas resuelven sus archivos con `Path(__file__).resolve().parent`,
  así que el proyecto se puede ejecutar desde cualquier directorio.

### 2. Retrieval — `chatbot.py` (clase `AsistenteFAQ`)

Búsqueda por recuperación de texto en 5 etapas, sin ninguna dependencia de
terceros:

1. **Preprocesamiento** — el texto se pasa a minúsculas, se le quitan las
   tildes (`unicodedata` NFD → se descartan los diacríticos), se tokeniza con
   `re.findall(r"[a-z0-9]+")` y se filtran las stopwords.
2. **Stemming liviano** — se recortan sufijos morfológicos (`-ar`, `-er`, `-ir`,
   `-ando`, `-cion`, `-mente`, …) con un mínimo de 4 caracteres restantes, para
   que `limpiar` / `limpieza` / `limpio` y `sillon` / `sillones` colapsen al
   mismo término.
3. **Indexación con pesos IDF** — cada raíz recibe un peso
   `log((N+1)/(df+1)) + 1` según cuántos documentos del FAQ la contienen. Los
   términos raros pesan más, así que las palabras genéricas (*"cuánto"*, *"pago"*)
   no dominan el ranking.
4. **Matching exacto + difuso** — primero se prueba la igualdad de raíces; si no
   hay, se acepta una similitud difusa (`difflib`) ≥ 0.85 ponderada al 70%.
   Así `madera` sigue encontrándose aunque el cliente escriba con otra
   terminación.
5. **Scoring** — `score = 0.7 × cobertura_ponderada_de_la_consulta + 0.3 ×
   cobertura_ponderada_del_documento`, y una **penalidad ×0.45** cuando hay una
   sola coincidencia (una única palabra en común no es evidencia suficiente).

> El documento indexado de cada entrada es la **unión de `pregunta` + `keywords`**,
> de modo que el usuario nunca tiene que saber la redacción oficial del FAQ.

### 3. Guardrail de fuera de tema

Si el mejor score queda por debajo del **umbral de 0.30**, el asistente no devuelve
la respuesta del FAQ sino un mensaje amable que:

- reconoce que no tiene esa información,
- reorienta al usuario listando los temas que sí cubre,
- ofrece el formulario de contacto como salida.

El contrato de la API lo hace explícito: la respuesta es `HTTP 200` con
`relevante: false` y `confianza` baja — no un error, porque para el usuario es
una respuesta válida. El frontend rotula esa burbuja como
*"Sin coincidencia en el FAQ · tema fuera de alcance"*.

### 4. Persistencia — SQLite

`POST /api/contacto` valida y escribe en `data/mensajes.db` (tabla `mensajes`:
`id`, `nombre`, `email`, `mensaje`, `creado_en`), e incluye un **campo trampa
anti-spam** llamado `categoria`: está oculto con `aria-hidden` y `tabindex="-1"`
en el HTML, por lo que un humano nunca lo completa, pero la mayoría de los bots
de spam sí. Si viene relleno, la API responde con el **mismo mensaje de éxito**
(para no revelar el filtro) pero con `id: null` y **no escribe nada en la base**.

### 5. Frontend — `static/`

- **Mobile-first**, tema oscuro moderno con acento verde menta.
- Sección hero, catálogo, chat con burbujas + indicador de escritura, formulario
  de contacto con validación en cliente, y **botón de chat flotante (FAB)**
  abajo a la derecha que abre un chat compacto (cerrable con `Esc`).
- Los chips de sugerencia se generan dinámicamente desde `GET /api/faq`.
- Media query en `<720px`: se oculta la navegación, la cabecera de statistics se
  compacta, los formularios pasan a una sola columna y el FAB se reduce a su ícono.
- `js/app.js` habla con la API con `fetch`, maneja errores de red por separado
  del error de negocio (burbuja roja) y muestra confirmación del contacto.

## Resultados

Suite de verificación de 20 consultas (**13 del dominio + 7 fuera de tema**),
ejecutada contra el retrieval:

| Métrica | Resultado |
|---|---|
| Aciertos (respuesta correcta **y** `relevante` correcto) | **20/20 — 100%** |
| Confianza media en consultas del dominio | **0.718** |
| Confianza máxima fuera de tema | **0.153** (umbral: 0.30) |
| Dependencias del retrieval | **0** (solo biblioteca estándar) |

El umbral de 0.30 separa los dos grupos sin solapamiento: la confianza media del
dominio es 0.718 y el peor caso fuera de tema queda en 0.153.

### Respuestas reales del API

**1) Consulta relevante — envíos** (`POST /api/chat`)

```json
{
  "respuesta": "Si, enviamos a todo el pais. El envio es gratis en compras superiores a $150.000 y tarda de 3 a 8 dias habiles segun la provincia. Los envios a domicilio incluyen subida a planta y coordinacion previa por WhatsApp.",
  "confianza": 0.759,
  "relevante": true,
  "pregunta_match": "Hacen envios a todo el pais?"
}
```

**2) Consulta relevante — devoluciones en lenguaje coloquial** (`POST /api/chat`)

```json
{
  "respuesta": "Tenes 30 dias calendario desde la entrega para devolver un producto sin uso y en su packaging original. La devolucion es gratuita y te emitimos el reembolso en un maximo de 10 dias habiles una vez recibido el producto en nuestro centro de distribucion.",
  "confianza": 0.7,
  "relevante": true,
  "pregunta_match": "Como funcionan las devoluciones?"
}
```

El usuario escribió `devolver` y `sillon`; el FAQ dice `devoluciones` y no
menciona sillones. El match funciona gracias al stemming (`devolv`) y a los
keywords, no a coincidencia literal.

**3) Consulta fuera de tema — guardrail** (`POST /api/chat`)

```json
{
  "respuesta": "Perdon, todavia no tengo informacion sobre eso. Como soy el asistente de CasaMuebles, lo mejor es consultarme por envios, garantia, materiales, devoluciones, formas de pago o armado de muebles. Si preferis hablar con una persona, podes usar el formulario de contacto de esta pagina.",
  "confianza": 0.0,
  "relevante": false,
  "pregunta_match": null
}
```

**4) Contacto guardado** (`POST /api/contacto` → `HTTP 201`)

```json
{
  "ok": true,
  "id": 3,
  "mensaje": "Consulta recibida. Te contactamos dentro de las 48 horas habiles."
}
```

Verificado en la tabla `mensajes` de `data/mensajes.db`:

```
(1, 'Mariana Gomez', 'mariana.gomez@ejemplo.com', 'Quisiera saber si el placard a medida entra en un departamento de 2 ambientes.', '2026-09-26T14:30:00+00:00')
(2, 'Diego Fernandez', 'diego.fernandez@ejemplo.com', 'Consulta por stock: necesito 2 comedores en 12 cuotas sin interes para un local comercial.', '2026-09-26T14:42:00+00:00')
```

**5) Validaciones y anti-spam**

| Caso | HTTP | Respuesta |
|---|---|---|
| Email inválido | `422` | `{"detail":"El email no tiene un formato valido."}` |
| Mensaje < 10 caracteres | `422` | `{"detail":[{"type":"string_too_short","loc":["body","mensaje"],...}]}` |
| Spam (`categoria` relleno) | `200` | `{"ok":true,"id":null,...}` → **no se guarda** |

### Flujo de una sesión completa

```
Navegador                     API (FastAPI)                  SQLite / retrieval
    │  GET /                     │                                  │
    ├───────────────────────────►│  sirve static/index.html         │
    │  GET /api/faq              │                                  │
    ├───────────────────────────►│─────────────────► carga faq.json, indexa 12 entradas
    │◄──────── 5 preguntas       │                                  │
    │                           │                                  │
    │  POST /api/chat            │                                  │
    │  {"message":"¿Hacen        │─── tokenizar + stemming ───────►│
    │   envíos a todo el país?"} │    scoring IDF × 5 documentos    │
    │                           │    score 0.759 > umbral 0.30      │
    │◄── {respuesta, confianza,  │                                  │
    │     relevante:true}       │                                  │
    │  [burbuja bot + metadato   │                                  │
    │   "confianza 0.759"]       │                                  │
    │                           │                                  │
    │  POST /api/chat            │                                  │
    │  {"message":"cómo armo     │    score 0.0 < umbral → guardrail │
    │   una pizza"}              │◄── respuesta amable + sugerencias│
    │◄── {relevante:false}      │                                  │
    │  [burbuja roja/gris con    │                                  │
    │   "tema fuera de alcance"] │                                  │
    │                           │                                  │
    │  POST /api/contacto        │  valida email + campo trampa     │
    ├───────────────────────────►│── INSERT INTO mensajes ─────────►│
    │◄── 201 {ok:true, id:3}     │                                  │
    │  [✓ "Te contactamos en      │                                  │
    │    48 horas habiles"]       │                                  │
    ▼
```

> El archivo `data/mensajes.db` se incluye commiteado con 2 mensajes de ejemplo
> para que se vea que la persistencia funciona sin tener que correr nada.

## Cómo reproducir

```bash
pip install -r requirements.txt
uvicorn app:app --port 8000
```

Abrir <http://127.0.0.1:8000> — la landing, el chat y el formulario están en la
misma página. La doc interactiva de la API queda en `/docs`.

### 3 comandos del API

```bash
# 1) Pregunta relevante al FAQ -> responde con confianza alta
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"Hacen envios a todo el pais?"}'

# 2) Pregunta fuera de tema -> guardrail: relevante=false
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message":"como armo una pizza"}'

# 3) Contacto -> valida y guarda en data/mensajes.db
curl -X POST http://127.0.0.1:8000/api/contacto \
  -H "Content-Type: application/json" \
  -d '{"nombre":"Mariana Gomez","email":"mariana.gomez@ejemplo.com","mensaje":"Quisiera saber si el placard a medida entra en un departamento de 2 ambientes.","categoria":""}'
```

En PowerShell los mismos comandos se pueden probar con `Invoke-RestMethod`
(ver `outputs/ejemplo_api.md`).

> El retrieval se puede probar sin levantar el servidor:
> `python chatbot.py` imprime 4 consultas de ejemplo con su score.

## Estructura

```
web-integracion-ia/
├── app.py                    # FastAPI: static + /api/chat + /api/contacto + SQLite
├── chatbot.py                # clase AsistenteFAQ: retrieval, IDF, guardrail
├── requirements.txt          # fastapi>=0.110, uvicorn>=0.29
├── data/
│   ├── faq.json              # 12 preguntas/respuestas + keywords
│   └── mensajes.db           # SQLite (2 contactos de ejemplo, commiteado)
├── static/
│   ├── index.html            # landing: hero, catálogo, chat, contacto
│   ├── css/
│   │   └── styles.css        # tema oscuro + acento menta, responsive
│   └── js/
│       └── app.js            # fetch al API, burbujas, FAB, formulario
└── outputs/
    └── ejemplo_api.md        # respuestas reales del API (curl/Invoke-WebRequest)
```

## Autor

Juan Pablo Contato — Licenciado en Ciencias de Datos
