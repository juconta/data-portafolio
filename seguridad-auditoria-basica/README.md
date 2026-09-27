# Auditoría y Arreglos Básicos de Ciberseguridad

Escáner **estático de seguridad** hecho solo con la librería estándar de Python
(sin dependencias externas) que detecta los errores de ciberseguridad más
comunes en una aplicación web, acompañado de una app FastAPI **vulnerable**,
su versión **corregida** y el informe profesional de auditoría con severidad y
prioridad.

## Problema

Una pyme de 10 personas casi nunca tiene equipo de seguridad: no hay nadie
dedicado a revisar el código antes de publicarlo. El resultado son errores que
un atacante encuentra en minutos, como la clave de la pasarela de pago escrita
dentro del propio archivo `.py`, un `.env` subido al repositorio, o un login sin
límite de intentos que permite adivinar contraseñas a fuerza bruta.

Contratar un pentest para una app de 50.000 USD cuesta más que la app misma. Este
proyecto demuestra que **con leer el código como texto** se puede detectar y
ordenar la mayoría de esos errores, y corregirlos uno por uno.

> **Alcance y ética:** el escaneo es 100 % local y estático. No se ejecuta el
> código auditado, no se prueban exploits y no se hace ninguna petición a
> servidores externos. Todo el código, las credenciales y los datos son
> ficticios y sirven solo como material de demostración.

## Qué incluye

| Pieza | Qué es |
|---|---|
| `escaner.py` | Escáner estático en Python estándar. Lee los archivos de texto y busca 19 patrones de riesgo + 11 chequeos de archivos sensibles. Devuelve código de salida 1 si hay hallazgos críticos, para poder encadenarlo en un pipeline. |
| `rules.json` | Las 19 reglas configurables: patrón, severidad, categoría, descripción y recomendación en lenguaje simple. Se pueden agregar o ajustar sin tocar el código. |
| `app_vulnerable/` | App FastAPI de ejemplo con 20 vulnerabilidades marcadas con `# VULNERABILIDAD`: API key hardcodeada, `.env` commiteado, CORS `*`, `debug=True`, `eval()`, `pickle`, SQL injection, login sin rate limit, cookies sin protección, MD5 para contraseñas y TLS sin verificar. |
| `app_segura/` | La misma app corregida 1 a 1: claves desde `os.environ`, CORS restringido, rate limit en memoria, PBKDF2 con sal, headers de seguridad con middleware de Starlette y tokens firmados con vencimiento. |
| `hallazgos/INFORME_AUDITORIA.md` | Informe final: resumen ejecutivo, tabla de hallazgos con evidencia `archivo:línea`, severidad, prioridad, plan de acción y el mapeo de cada corrección. |
| `outputs/resumen_escaneo.txt` | Salida de consola del escáner, antes y después de las correcciones. |

## Proceso

1. **Catálogo de reglas** → se definieron 19 patrones (secretos, `debug`, CORS,
   `eval`/`exec`, `pickle`, SQL injection, cookies, TLS, `print`) más 11 patrones
   de archivos que no deben subirse al repositorio (`.env`, `*.pem`, `*.db`...).
   Cada regla tiene severidad y una explicación pensada para un dueño de pyme.
2. **Escaneo de la app vulnerable** → `python escaner.py app_vulnerable --reporte
   hallazgos/INFORME_AUDITORIA.md`. El escáner recorre los `.py` y los archivos de
   entorno, saltea los comentarios y agrupa los hallazgos por archivo, archivo y
   línea.
3. **Priorización** → cada severidad se traduce a una prioridad de negocio:
   `CRÍTICA` = P0 (hoy mismo), `ALTA` = P1 (esta semana), `MEDIA` = P2 (próximo
   sprint), `BAJA` = P3 (cuando se pueda).
4. **Corrección** → se reescribió la app en `app_segura/` aplicando cada
   recomendación del informe.
5. **Verificación** → al volver a escanear, la app corregida da **0 hallazgos**.

## Resultados

Escaneo real de `app_vulnerable`: **29 hallazgos** → **8 críticos, 11 altos,
7 medios y 3 bajos**. Detalle completo en
[`hallazgos/INFORME_AUDITORIA.md`](hallazgos/INFORME_AUDITORIA.md).

| ID | Severidad | Hallazgo | Ocurrencias | Estado |
|---|---|---|---|---|
| ARCH-SENS | CRÍTICA | `.env` con claves reales versionado | 1 | Corregido |
| SEC-001 | CRÍTICA | Clave de API escrita en el código | 2 | Corregido |
| SEC-003 | CRÍTICA | CORS `*` abierto junto con credenciales | 1 | Corregido |
| SEC-004 | CRÍTICA | `eval()` sobre datos enviados por el cliente | 1 | Corregido |
| SEC-005 | CRÍTICA | Secretos con valor real dentro del `.env` | 3 | Corregido |
| SEC-006 | ALTA | Contraseña por defecto en el código | 1 | Corregido |
| SEC-007 | ALTA | Modo debug activado | 3 | Corregido |
| SEC-008 | ALTA | `pickle.loads()` sobre datos recibidos | 1 | Corregido |
| SEC-009 | ALTA | Consulta SQL armada por concatenación | 1 | Corregido |
| SEC-010 | ALTA | Login sin límite de intentos | 1 | Corregido |
| SEC-011 | ALTA | `ALLOWED_HOSTS = ["*"]` | 1 | Corregido |
| SEC-012 | ALTA | `.env.example` con valores reales | 3 | Corregido |
| SEC-013 | MEDIA | MD5 para contraseñas | 1 | Corregido |
| SEC-014 | MEDIA | Cookie de sesión sin banderas | 1 | Corregido |
| SEC-015 | MEDIA | Sin headers de seguridad HTTP | 1 | Corregido |
| SEC-016 | MEDIA | Detalle interno del error al cliente | 1 | Corregido |
| SEC-017 | MEDIA | Conexión sin verificar el certificado TLS | 1 | Corregido |
| SEC-018 | MEDIA | Métodos y headers CORS abiertos | 2 | Corregido |
| SEC-019 | BAJA | `print()` de depuración en producción | 3 | Corregido |

- **Todos los hallazgos quedaron corregidos**: `python escaner.py app_segura`
  devuelve `0` en las cuatro severidades.
- Los casos críticos ilustran el riesgo real de una pyme: secretos escritos en
  el código, un `.env` versionado con la contraseña de la base, un `eval()` que
  ejecuta código en el servidor y un CORS abierto que permite el robo de sesión
  desde cualquier web.
- Correcciones destacadas: PBKDF2-HMAC-SHA256 con sal por usuario y comparación
  en tiempo constante, tokens de sesión firmados con HMAC y vencimiento de 30
  minutos, y un middleware de Starlette que agrega `Strict-Transport-Security`,
  `X-Content-Type-Options` y `X-Frame-Options` a cada respuesta.
- Comprobado en ejecución: la app corregida responde `200` en `GET /`, con los 6
  headers de seguridad presentes; el login bloquea con `HTTP 429` al sexto
  intento fallido; y `/calcular` rechaza operaciones fuera de la lista blanca.

## Cómo reproducir

El escáner **no necesita instalar nada** (solo Python 3.10+). Para correr las apps
de ejemplo hace falta FastAPI:

```bash
# 1. Escanear la app vulnerable y generar el informe
python escaner.py app_vulnerable --reporte hallazgos/INFORME_AUDITORIA.md

# 2. Verificar la app corregida (debe dar 0 hallazgos y salir con código 0)
python escaner.py app_segura

# Opcional: ver solo los hallazgos críticos o de mayor severidad
python escaner.py app_vulnerable --min-severidad CRITICA

# Opcional: las apps de ejemplo
pip install -r requirements.txt
uvicorn app_vulnerable.app:app --port 8013
uvicorn app_segura.app:app --port 8014
```

> El escáner devuelve código de salida **1** cuando encuentra hallazgos críticos
> y **0** cuando no, así que se puede usar como paso de un pipeline: si el
> código es 1, el build falla. Al regenerar el informe, el escáner respeta el
> marcador `<!-- ANEXO-MANUAL -->` y conserva la sección escrita a mano.

## Estructura

```
seguridad-auditoria-basica/
├── escaner.py                     # escáner estático (solo librería estándar)
├── rules.json                     # 19 reglas + 11 patrones de archivos sensibles
├── app_vulnerable/
│   ├── app.py                     # app FastAPI con 20 vulnerabilidades marcadas
│   ├── .env                       # archivo de entorno con claves reales (el problema)
│   └── .env.example               # plantilla con valores reales (también el problema)
├── app_segura/
│   ├── app.py                     # la misma app, corregida
│   └── .env.example               # plantilla clara, con valores vacíos
├── hallazgos/
│   └── INFORME_AUDITORIA.md       # informe final (secciones 1-6 automáticas + 7 manual)
├── outputs/
│   └── resumen_escaneo.txt        # salida de consola del escáner
└── requirements.txt               # solo para las apps de ejemplo
```

## Autor

Juan Pablo Contato — Licenciado en Ciencias de Datos
