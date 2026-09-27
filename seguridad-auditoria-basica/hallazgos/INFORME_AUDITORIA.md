# Informe de auditoria de seguridad - app_vulnerable

| Dato | Valor |
|---|---|
| Fecha | 2026-09-26 13:16 |
| Carpeta analizada | `app_vulnerable` |
| Archivos de codigo revisados | 3 |
| Reglas aplicadas | 19 patrones + 11 chequeos de archivos |
| Reglas desde | `rules.json` |
| Total de hallazgos | 29 |
| Opinion | **NO APTO PARA PRODUCCION** |

> Analisis estatico: no se ejecuto el codigo auditado ni se realizo ninguna prueba de ataque contra un sistema. Todo se resolvio leyendo los archivos de texto.

## 1. Resumen ejecutivo

Este informe es el resultado de pasar el escaner estatico sobre `app_vulnerable`. El escaner lee el codigo como texto y busca los errores de seguridad mas comunes: claves escondidas en el codigo, archivos de configuracion que no deberian subirse, funciones que ejecutan codigo recibido por Internet, contrasenas de fabrica y falta de controles basicos en el login.

**Resultado: NO APTO PARA PRODUCCION** - Hay problemas criticos que permiten alcanzar robo de datos o ejecutar codigo en el servidor. Hay que corregirlos antes de publicar la aplicacion.

Se detectaron **29 problemas** en total: **8 criticos**, 11 altos, 7 medios y 3 bajos.

### Que significa esto para el negocio

Los 8 problemas criticos incluyen: archivo .env versionado en el repositorio, cors abierto a cualquier origen y con credenciales, ejecucion de codigo escrita por el usuario (eval / exec), secreto con valor real dentro de un archivo .env, secreto o clave de api escrita en el codigo.
En la practica, esto significa que una persona no autorizada podria entrar al panel, leer datos de clientes o ejecutar acciones usando informacion que ya esta publicada en el propio repositorio.

Entre los riesgos altos mas relevantes estan: consulta sql armada por concatenacion de texto, contrasena o clave por defecto escrita en el codigo, deserializacion insegura (pickle / yaml.load), endpoint de autenticacion sin control de intentos (rate limit).

## 2. Conteo por severidad

| Severidad | Cantidad | Prioridad | Significado |
|---|---|---|---|
| CRITICA | 8 | P0 - Inmediata (hoy mismo) | Se puede llegar a datos o control del servidor. Corregir ya. |
| ALTA | 11 | P1 - Alta (esta semana) | Facilita ataques comunes (fuerza bruta, robo de clave). Corregir esta semana. |
| MEDIA | 7 | P2 - Media (proximo sprint) | Buenas practicas que reducen el riesgo. Corregir en el proximo sprint. |
| BAJA | 3 | P3 - Planeada (cuando se pueda) | Higiene de codigo. Anotado para limpiar cuando se pueda. |

## 3. Hallazgos detallados

| ID | Severidad | Prioridad | Hallazgo | Ubicacion | Evidencia |
|---|---|---|---|---|---|
| ARCH-SENS | CRITICA | P0 - Inmediata (hoy mismo) | Archivo .env versionado en el repositorio | `.env` | `archivo presente: .env` |
| SEC-005 | CRITICA | P0 - Inmediata (hoy mismo) | Secreto con valor real dentro de un archivo .env | `.env:5` | `DB_PASSWORD=admin123` |
| SEC-005 | CRITICA | P0 - Inmediata (hoy mismo) | Secreto con valor real dentro de un archivo .env | `.env:8` | `API_KEY=sk_EJEMPLO_REDACTADO_PARA_REPO_PUBLICO` |
| SEC-005 | CRITICA | P0 - Inmediata (hoy mismo) | Secreto con valor real dentro de un archivo .env | `.env:9` | `SECRET_JWT=jwt_supersecreto_de_la_app_2024` |
| SEC-001 | CRITICA | P0 - Inmediata (hoy mismo) | Secreto o clave de API escrita en el codigo | `app.py:33` | `API_KEY_GLOBAL = "sk_EJEMPLO_REDACTADO_PARA_REPO_PUBLICO" # VULNERABILIDAD` |
| SEC-001 | CRITICA | P0 - Inmediata (hoy mismo) | Secreto o clave de API escrita en el codigo | `app.py:34` | `SECRET_KEY = "clave-de-sesion-supersecreta-2024" # VULNERABILIDAD` |
| SEC-003 | CRITICA | P0 - Inmediata (hoy mismo) | CORS abierto a cualquier origen y con credenciales | `app.py:51` | `allow_origins=["*"], # VULNERABILIDAD: cualquier sitio web puede llamar la API allow_credentials=True` |
| SEC-004 | CRITICA | P0 - Inmediata (hoy mismo) | Ejecucion de codigo escrita por el usuario (eval / exec) | `app.py:159` | `return {"resultado": eval(expresion)} # VULNERABILIDAD` |
| SEC-007 | ALTA | P1 - Alta (esta semana) | Modo debug activado | `.env:10` | `DEBUG=True` |
| SEC-012 | ALTA | P1 - Alta (esta semana) | Valores de ejemplo que en realidad son secretos (.env.example) | `.env.example:6` | `DB_PASSWORD=Admin123` |
| SEC-012 | ALTA | P1 - Alta (esta semana) | Valores de ejemplo que en realidad son secretos (.env.example) | `.env.example:9` | `API_KEY=sk_EJEMPLO_REDACTADO_PARA_REPO_PUBLICO` |
| SEC-012 | ALTA | P1 - Alta (esta semana) | Valores de ejemplo que en realidad son secretos (.env.example) | `.env.example:10` | `SECRET_JWT=cambiar_esto_en_produccion` |
| SEC-007 | ALTA | P1 - Alta (esta semana) | Modo debug activado | `.env.example:11` | `DEBUG=True` |
| SEC-006 | ALTA | P1 - Alta (esta semana) | Contrasena o clave por defecto escrita en el codigo | `app.py:35` | `DB_PASSWORD = "admin123" # VULNERABILIDAD: contrasena de fabrica` |
| SEC-007 | ALTA | P1 - Alta (esta semana) | Modo debug activado | `app.py:40` | `DEBUG = True # VULNERABILIDAD: en produccion muestra trazas internas` |
| SEC-011 | ALTA | P1 - Alta (esta semana) | Host permitido con comodin (ALLOWED_HOSTS = ['*']) | `app.py:41` | `ALLOWED_HOSTS = ["*"] # VULNERABILIDAD: responde en cualquier dominio` |
| SEC-010 | ALTA | P1 - Alta (esta semana) | Endpoint de autenticacion sin control de intentos (rate limit) | `app.py:110` | `@app.post("/login")` |
| SEC-009 | ALTA | P1 - Alta (esta semana) | Consulta SQL armada por concatenacion de texto | `app.py:123` | `execute( f"SELECT id, nombre, password_hash FROM usuarios WHERE email = '{` |
| SEC-008 | ALTA | P1 - Alta (esta semana) | Deserializacion insegura (pickle / yaml.load) | `app.py:170` | `return {"config": pickle.loads(datos)} # VULNERABILIDAD` |
| SEC-015 | MEDIA | P2 - Media (proximo sprint) | Sin headers de seguridad HTTP | `app.py:43` | `app = FastAPI(title="API Demo Vulnerable", version="0.1.0", debug=DEBUG)` |
| SEC-018 | MEDIA | P2 - Media (proximo sprint) | Metodos y headers CORS abiertos a todo | `app.py:53` | `allow_methods=["*"], # VULNERABILIDAD: cualquier metodo HTTP` |
| SEC-018 | MEDIA | P2 - Media (proximo sprint) | Metodos y headers CORS abiertos a todo | `app.py:54` | `allow_headers=["*"], # VULNERABILIDAD: cualquier cabecera` |
| SEC-013 | MEDIA | P2 - Media (proximo sprint) | Hash debil para contrasenas (MD5 / SHA1) | `app.py:68` | `return hashlib.md5((password + "salt").encode()).hexdigest()` |
| SEC-014 | MEDIA | P2 - Media (proximo sprint) | Cookie de sesion sin banderas de proteccion | `app.py:137` | `"sesion", token_de_sesion(email), httponly=False, secure=False, samesite="none"` |
| SEC-016 | MEDIA | P2 - Media (proximo sprint) | Detalle interno del error expuesto al cliente | `app.py:186` | `raise HTTPException(status_code=500, detail=str(error))` |
| SEC-017 | MEDIA | P2 - Media (proximo sprint) | Conexion sin verificar el certificado TLS | `app.py:195` | `contexto = ssl._create_unverified_context() # VULNERABILIDAD` |
| SEC-019 | BAJA | P3 - Planeada (cuando se pueda) | Sentencias print() de depuracion en codigo de aplicacion | `app.py:128` | `print(f"[DEBUG] login fallido para {email} desde {request.client.host}")` |
| SEC-019 | BAJA | P3 - Planeada (cuando se pueda) | Sentencias print() de depuracion en codigo de aplicacion | `app.py:131` | `print(f"[DEBUG] login correcto de {fila['nombre']} desde {request.client.host}")` |
| SEC-019 | BAJA | P3 - Planeada (cuando se pueda) | Sentencias print() de depuracion en codigo de aplicacion | `app.py:185` | `print(f"[DEBUG] error en reportes: {error}")` |

## 4. Que hacer y en que orden

1. **[ARCH-SENS] Archivo .env versionado en el repositorio** - CRITICA / P0 - Inmediata (hoy mismo).  Archivos: `.env`.
   Como se corrige: Borrar el archivo del repositorio, agregar '.env' al .gitignore y rotar (cambiar) todas las claves que estaban dentro.
2. **[SEC-005] Secreto con valor real dentro de un archivo .env** - CRITICA / P0 - Inmediata (hoy mismo) (3 ubicaciones).  Archivos: `.env`.
   Como se corrige: Borrar el .env del repositorio, ignorarlo en el .gitignore, cargar los valores desde el gestor de secretos del hosting y rotar la clave expuesta.
3. **[SEC-001] Secreto o clave de API escrita en el codigo** - CRITICA / P0 - Inmediata (hoy mismo) (2 ubicaciones).  Archivos: `app.py`.
   Como se corrige: Leer la clave desde una variable de entorno (os.getenv) y guardarla en el gestor de secretos del hosting. Luego rotar la clave expuesta.
4. **[SEC-003] CORS abierto a cualquier origen y con credenciales** - CRITICA / P0 - Inmediata (hoy mismo).  Archivos: `app.py`.
   Como se corrige: Reemplazar el '*' por la lista de dominios propios (ej. https://app.miempresa.com) y mantener allow_credentials=True solo con esa lista.
5. **[SEC-004] Ejecucion de codigo escrita por el usuario (eval / exec)** - CRITICA / P0 - Inmediata (hoy mismo).  Archivos: `app.py`.
   Como se corrige: Sacar eval/exec y reemplazar por una lista blanca (whitelist) de operaciones permitidas, o por un parser matematico seguro.
6. **[SEC-007] Modo debug activado** - ALTA / P1 - Alta (esta semana) (3 ubicaciones).  Archivos: `.env`, `.env.example`, `app.py`.
   Como se corrige: Dejar debug=False en produccion y activarlo solo en el entorno de desarrollo, controlado por una variable de entorno.
7. **[SEC-012] Valores de ejemplo que en realidad son secretos (.env.example)** - ALTA / P1 - Alta (esta semana) (3 ubicaciones).  Archivos: `.env.example`.
   Como se corrige: Dejar los valores vacios (API_KEY=) y poner solo la instruccion de como completarlos, para que nadie copie un valor real.
8. **[SEC-006] Contrasena o clave por defecto escrita en el codigo** - ALTA / P1 - Alta (esta semana).  Archivos: `app.py`.
   Como se corrige: Leer la contrasena desde una variable de entorno, generar contrasenas aleatorias para el alta de usuarios y no usar valores de fabrica.
9. **[SEC-011] Host permitido con comodin (ALLOWED_HOSTS = ['*'])** - ALTA / P1 - Alta (esta semana).  Archivos: `app.py`.
   Como se corrige: Limitar a los dominios reales (por ejemplo ['app.miempresa.com', 'localhost']) y activar validacion de Host con TrustedHostMiddleware.
10. **[SEC-010] Endpoint de autenticacion sin control de intentos (rate limit)** - ALTA / P1 - Alta (esta semana).  Archivos: `app.py`.
   Como se corrige: Agregar un rate limit en memoria o con libreria (por ejemplo 5 intentos por minuto y por IP), devolver HTTP 429 y registrar los fallos.
11. **[SEC-009] Consulta SQL armada por concatenacion de texto** - ALTA / P1 - Alta (esta semana).  Archivos: `app.py`.
   Como se corrige: Usar consultas parametrizadas: execute('SELECT ... WHERE email = ?', (email,)) y nunca interpolar variables con f-strings.
12. **[SEC-008] Deserializacion insegura (pickle / yaml.load)** - ALTA / P1 - Alta (esta semana).  Archivos: `app.py`.
   Como se corrige: Usar json para intercambiar datos o, con YAML, usar yaml.safe_load.
13. **[SEC-015] Sin headers de seguridad HTTP** - MEDIA / P2 - Media (proximo sprint).  Archivos: `app.py`.
   Como se corrige: Agregar un middleware de Starlette que anada esos headers a cada respuesta (ver app_segura/app.py).
14. **[SEC-018] Metodos y headers CORS abiertos a todo** - MEDIA / P2 - Media (proximo sprint) (2 ubicaciones).  Archivos: `app.py`.
   Como se corrige: Declarar solo los metodos y headers que la app usa realmente (ej. ['GET', 'POST'] y ['Authorization', 'Content-Type']).
15. **[SEC-013] Hash debil para contrasenas (MD5 / SHA1)** - MEDIA / P2 - Media (proximo sprint).  Archivos: `app.py`.
   Como se corrige: Usar bcrypt, scrypt o argon2 (o al menos hashlib.pbkdf2_hmac con muchas iteraciones y sal por usuario).
16. **[SEC-014] Cookie de sesion sin banderas de proteccion** - MEDIA / P2 - Media (proximo sprint).  Archivos: `app.py`.
   Como se corrige: Usar httponly=True, secure=True y samesite='lax' o 'strict', y poner la cookie con prefijo __Host-.
17. **[SEC-016] Detalle interno del error expuesto al cliente** - MEDIA / P2 - Media (proximo sprint).  Archivos: `app.py`.
   Como se corrige: Registrar la excepcion en el log del servidor (logging) y responder al cliente con un mensaje generico y un codigo de error interno.
18. **[SEC-017] Conexion sin verificar el certificado TLS** - MEDIA / P2 - Media (proximo sprint).  Archivos: `app.py`.
   Como se corrige: Usar la verificacion normal de TLS. Si hace falta un certificado interno, agregar su CA al almacen del sistema en vez de desactivar el control.
19. **[SEC-019] Sentencias print() de depuracion en codigo de aplicacion** - BAJA / P3 - Planeada (cuando se pueda) (3 ubicaciones).  Archivos: `app.py`.
   Como se corrige: Reemplazar por el modulo logging con niveles (info, warning, error) y revisar que no se registren contrasenas ni tokens.

## 5. Detalle tecnico por hallazgo

### 1. ARCH-SENS - Archivo .env versionado en el repositorio

- **Severidad:** CRITICA (P0 - Inmediata (hoy mismo))
- **Categoria:** Secretos
- **Ocurrencias:** 1 ubicacion(es) en 1 archivo(s)
- **Por que importa:** El archivo .env guarda las claves reales del proyecto y esta guardado en el repositorio. Cualquiera que tenga acceso al codigo puede leerlas.
- **Como se corrige:** Borrar el archivo del repositorio, agregar '.env' al .gitignore y rotar (cambiar) todas las claves que estaban dentro.

| Archivo | Linea | Evidencia |
|---|---|---|
| `.env` | - | `archivo presente: .env` |

### 2. SEC-005 - Secreto con valor real dentro de un archivo .env

- **Severidad:** CRITICA (P0 - Inmediata (hoy mismo))
- **Categoria:** Secretos
- **Ocurrencias:** 3 ubicacion(es) en 1 archivo(s)
- **Por que importa:** El archivo de entorno tiene el valor real de una clave o contrasena, y ademas esta guardado en el repositorio. Con solo clonar el proyecto alcanza para obtenerlo.
- **Como se corrige:** Borrar el .env del repositorio, ignorarlo en el .gitignore, cargar los valores desde el gestor de secretos del hosting y rotar la clave expuesta.

| Archivo | Linea | Evidencia |
|---|---|---|
| `.env` | 5 | `DB_PASSWORD=admin123` |
| `.env` | 8 | `API_KEY=sk_EJEMPLO_REDACTADO_PARA_REPO_PUBLICO` |
| `.env` | 9 | `SECRET_JWT=jwt_supersecreto_de_la_app_2024` |

### 3. SEC-001 - Secreto o clave de API escrita en el codigo

- **Severidad:** CRITICA (P0 - Inmediata (hoy mismo))
- **Categoria:** Secretos
- **Ocurrencias:** 2 ubicacion(es) en 1 archivo(s)
- **Por que importa:** Hay una clave o token escrita directamente en el archivo de codigo. Se lee como un texto normal, asi que cualquiera con acceso al repositorio la obtiene al instante.
- **Como se corrige:** Leer la clave desde una variable de entorno (os.getenv) y guardarla en el gestor de secretos del hosting. Luego rotar la clave expuesta.

| Archivo | Linea | Evidencia |
|---|---|---|
| `app.py` | 33 | `API_KEY_GLOBAL = "sk_EJEMPLO_REDACTADO_PARA_REPO_PUBLICO" # VULNERABILIDAD` |
| `app.py` | 34 | `SECRET_KEY = "clave-de-sesion-supersecreta-2024" # VULNERABILIDAD` |

### 4. SEC-003 - CORS abierto a cualquier origen y con credenciales

- **Severidad:** CRITICA (P0 - Inmediata (hoy mismo))
- **Categoria:** Acceso a la API
- **Ocurrencias:** 1 ubicacion(es) en 1 archivo(s)
- **Por que importa:** La API acepta peticiones desde CUALQUIER pagina web y ademas envia credenciales. Un atacante puede poner un sitio falso que robe la sesion del usuario con un simple formulario.
- **Como se corrige:** Reemplazar el '*' por la lista de dominios propios (ej. https://app.miempresa.com) y mantener allow_credentials=True solo con esa lista.

| Archivo | Linea | Evidencia |
|---|---|---|
| `app.py` | 51 | `allow_origins=["*"], # VULNERABILIDAD: cualquier sitio web puede llamar la API allow_credentials=True` |

### 5. SEC-004 - Ejecucion de codigo escrita por el usuario (eval / exec)

- **Severidad:** CRITICA (P0 - Inmediata (hoy mismo))
- **Categoria:** Codigo inseguro
- **Ocurrencias:** 1 ubicacion(es) en 1 archivo(s)
- **Por que importa:** La aplicacion ejecuta como codigo lo que recibe del cliente. Con esto, cualquiera que pueda llamar al endpoint puede ejecutar comandos en el servidor.
- **Como se corrige:** Sacar eval/exec y reemplazar por una lista blanca (whitelist) de operaciones permitidas, o por un parser matematico seguro.

| Archivo | Linea | Evidencia |
|---|---|---|
| `app.py` | 159 | `return {"resultado": eval(expresion)} # VULNERABILIDAD` |

### 6. SEC-007 - Modo debug activado

- **Severidad:** ALTA (P1 - Alta (esta semana))
- **Categoria:** Configuracion
- **Ocurrencias:** 3 ubicacion(es) en 1 archivo(s)
- **Por que importa:** Con el modo debug prendido, cualquier error muestra trazas internas (rutas del servidor, librerias, a veces valores de variables) al visitante.
- **Como se corrige:** Dejar debug=False en produccion y activarlo solo en el entorno de desarrollo, controlado por una variable de entorno.

| Archivo | Linea | Evidencia |
|---|---|---|
| `.env` | 10 | `DEBUG=True` |
| `.env.example` | 11 | `DEBUG=True` |
| `app.py` | 40 | `DEBUG = True # VULNERABILIDAD: en produccion muestra trazas internas` |

### 7. SEC-012 - Valores de ejemplo que en realidad son secretos (.env.example)

- **Severidad:** ALTA (P1 - Alta (esta semana))
- **Categoria:** Secretos
- **Ocurrencias:** 3 ubicacion(es) en 1 archivo(s)
- **Por que importa:** El archivo de ejemplo trae valores reales en vez de valores vacios. Los desarrolladores terminan usarlos tal cual y la clave queda igual de expuesta.
- **Como se corrige:** Dejar los valores vacios (API_KEY=) y poner solo la instruccion de como completarlos, para que nadie copie un valor real.

| Archivo | Linea | Evidencia |
|---|---|---|
| `.env.example` | 6 | `DB_PASSWORD=Admin123` |
| `.env.example` | 9 | `API_KEY=sk_EJEMPLO_REDACTADO_PARA_REPO_PUBLICO` |
| `.env.example` | 10 | `SECRET_JWT=cambiar_esto_en_produccion` |

### 8. SEC-006 - Contrasena o clave por defecto escrita en el codigo

- **Severidad:** ALTA (P1 - Alta (esta semana))
- **Categoria:** Secretos
- **Ocurrencias:** 1 ubicacion(es) en 1 archivo(s)
- **Por que importa:** Hay contrasenas de ejemplo o de fabrica dentro del proyecto. Los atacantes prueban siempre las contrasenas mas comunes (admin, 123456, password).
- **Como se corrige:** Leer la contrasena desde una variable de entorno, generar contrasenas aleatorias para el alta de usuarios y no usar valores de fabrica.

| Archivo | Linea | Evidencia |
|---|---|---|
| `app.py` | 35 | `DB_PASSWORD = "admin123" # VULNERABILIDAD: contrasena de fabrica` |

### 9. SEC-011 - Host permitido con comodin (ALLOWED_HOSTS = ['*'])

- **Severidad:** ALTA (P1 - Alta (esta semana))
- **Categoria:** Configuracion
- **Ocurrencias:** 1 ubicacion(es) en 1 archivo(s)
- **Por que importa:** La aplicacion responde a cualquier nombre de dominio. Eso permite cambiar el dominio en un enlace para generar paginas de phishing o para capturar contrasenas con formularios falsos.
- **Como se corrige:** Limitar a los dominios reales (por ejemplo ['app.miempresa.com', 'localhost']) y activar validacion de Host con TrustedHostMiddleware.

| Archivo | Linea | Evidencia |
|---|---|---|
| `app.py` | 41 | `ALLOWED_HOSTS = ["*"] # VULNERABILIDAD: responde en cualquier dominio` |

### 10. SEC-010 - Endpoint de autenticacion sin control de intentos (rate limit)

- **Severidad:** ALTA (P1 - Alta (esta semana))
- **Categoria:** Acceso
- **Ocurrencias:** 1 ubicacion(es) en 1 archivo(s)
- **Por que importa:** El endpoint de login no tiene ningun limite de peticiones. Un atacante puede probar miles de contrasenas por minuto hasta adivinar la cuenta.
- **Como se corrige:** Agregar un rate limit en memoria o con libreria (por ejemplo 5 intentos por minuto y por IP), devolver HTTP 429 y registrar los fallos.

| Archivo | Linea | Evidencia |
|---|---|---|
| `app.py` | 110 | `@app.post("/login")` |

### 11. SEC-009 - Consulta SQL armada por concatenacion de texto

- **Severidad:** ALTA (P1 - Alta (esta semana))
- **Categoria:** Inyeccion
- **Ocurrencias:** 1 ubicacion(es) en 1 archivo(s)
- **Por que importa:** La consulta SQL se arma metiendo el texto del usuario dentro de la cadena. Un atacante puede escribir comillas para leer o borrar la base de datos (inyeccion SQL).
- **Como se corrige:** Usar consultas parametrizadas: execute('SELECT ... WHERE email = ?', (email,)) y nunca interpolar variables con f-strings.

| Archivo | Linea | Evidencia |
|---|---|---|
| `app.py` | 123 | `execute( f"SELECT id, nombre, password_hash FROM usuarios WHERE email = '{` |

### 12. SEC-008 - Deserializacion insegura (pickle / yaml.load)

- **Severidad:** ALTA (P1 - Alta (esta semana))
- **Categoria:** Datos
- **Ocurrencias:** 1 ubicacion(es) en 1 archivo(s)
- **Por que importa:** Deserializar con pickle o con yaml.load sin proteccion permite que los datos recibidos ejecuten codigo en el servidor.
- **Como se corrige:** Usar json para intercambiar datos o, con YAML, usar yaml.safe_load.

| Archivo | Linea | Evidencia |
|---|---|---|
| `app.py` | 170 | `return {"config": pickle.loads(datos)} # VULNERABILIDAD` |

### 13. SEC-015 - Sin headers de seguridad HTTP

- **Severidad:** MEDIA (P2 - Media (proximo sprint))
- **Categoria:** Configuracion
- **Ocurrencias:** 1 ubicacion(es) en 1 archivo(s)
- **Por que importa:** La app no envia headers como X-Content-Type-Options, Strict-Transport-Security ni X-Frame-Options. Eso deja la puerta abierta a secuestros de sesion, HTTPS editado y clickjacking.
- **Como se corrige:** Agregar un middleware de Starlette que anada esos headers a cada respuesta (ver app_segura/app.py).

| Archivo | Linea | Evidencia |
|---|---|---|
| `app.py` | 43 | `app = FastAPI(title="API Demo Vulnerable", version="0.1.0", debug=DEBUG)` |

### 14. SEC-018 - Metodos y headers CORS abiertos a todo

- **Severidad:** MEDIA (P2 - Media (proximo sprint))
- **Categoria:** Acceso a la API
- **Ocurrencias:** 2 ubicacion(es) en 1 archivo(s)
- **Por que importa:** Se permiten todos los metodos HTTP y todos los headers desde cualquier origen. Aumenta la superficie de ataque de la API.
- **Como se corrige:** Declarar solo los metodos y headers que la app usa realmente (ej. ['GET', 'POST'] y ['Authorization', 'Content-Type']).

| Archivo | Linea | Evidencia |
|---|---|---|
| `app.py` | 53 | `allow_methods=["*"], # VULNERABILIDAD: cualquier metodo HTTP` |
| `app.py` | 54 | `allow_headers=["*"], # VULNERABILIDAD: cualquier cabecera` |

### 15. SEC-013 - Hash debil para contrasenas (MD5 / SHA1)

- **Severidad:** MEDIA (P2 - Media (proximo sprint))
- **Categoria:** Criptografia
- **Ocurrencias:** 1 ubicacion(es) en 1 archivo(s)
- **Por que importa:** MD5 y SHA1 fueron disenados para velocidad, no para guardar contrasenas. Se rompen en segundos con una PC moderna, asi que un robo de la base de datos equivale a tener todas las contrasenas.
- **Como se corrige:** Usar bcrypt, scrypt o argon2 (o al menos hashlib.pbkdf2_hmac con muchas iteraciones y sal por usuario).

| Archivo | Linea | Evidencia |
|---|---|---|
| `app.py` | 68 | `return hashlib.md5((password + "salt").encode()).hexdigest()` |

### 16. SEC-014 - Cookie de sesion sin banderas de proteccion

- **Severidad:** MEDIA (P2 - Media (proximo sprint))
- **Categoria:** Sesiones
- **Ocurrencias:** 1 ubicacion(es) en 1 archivo(s)
- **Por que importa:** La cookie de sesion no esta protegida: se puede leer desde JavaScript y se envia sin cifrar, con lo que queda expuesta ante robo de sesion.
- **Como se corrige:** Usar httponly=True, secure=True y samesite='lax' o 'strict', y poner la cookie con prefijo __Host-.

| Archivo | Linea | Evidencia |
|---|---|---|
| `app.py` | 137 | `"sesion", token_de_sesion(email), httponly=False, secure=False, samesite="none"` |

### 17. SEC-016 - Detalle interno del error expuesto al cliente

- **Severidad:** MEDIA (P2 - Media (proximo sprint))
- **Categoria:** Informacion filtrada
- **Ocurrencias:** 1 ubicacion(es) en 1 archivo(s)
- **Por que importa:** Al cliente se le devuelve el mensaje crudo de la excepcion. Sirve de mapa para el atacante: revela nombres de tablas, rutas del servidor y librerias instaladas.
- **Como se corrige:** Registrar la excepcion en el log del servidor (logging) y responder al cliente con un mensaje generico y un codigo de error interno.

| Archivo | Linea | Evidencia |
|---|---|---|
| `app.py` | 186 | `raise HTTPException(status_code=500, detail=str(error))` |

### 18. SEC-017 - Conexion sin verificar el certificado TLS

- **Severidad:** MEDIA (P2 - Media (proximo sprint))
- **Categoria:** Transporte
- **Ocurrencias:** 1 ubicacion(es) en 1 archivo(s)
- **Por que importa:** La app se conecta aceptando cualquier certificado. Un atacante en la red puede leer y modificar lo que la aplicacion envia o recibe (ataque intermediario).
- **Como se corrige:** Usar la verificacion normal de TLS. Si hace falta un certificado interno, agregar su CA al almacen del sistema en vez de desactivar el control.

| Archivo | Linea | Evidencia |
|---|---|---|
| `app.py` | 195 | `contexto = ssl._create_unverified_context() # VULNERABILIDAD` |

### 19. SEC-019 - Sentencias print() de depuracion en codigo de aplicacion

- **Severidad:** BAJA (P3 - Planeada (cuando se pueda))
- **Categoria:** Calidad
- **Ocurrencias:** 3 ubicacion(es) en 1 archivo(s)
- **Por que importa:** Hay print() de depuracion. No es una vulnerabilidad en si, pero ensucia los logs y suele terminar mostrando datos sensibles en consola.
- **Como se corrige:** Reemplazar por el modulo logging con niveles (info, warning, error) y revisar que no se registren contrasenas ni tokens.

| Archivo | Linea | Evidencia |
|---|---|---|
| `app.py` | 128 | `print(f"[DEBUG] login fallido para {email} desde {request.client.host}")` |
| `app.py` | 131 | `print(f"[DEBUG] login correcto de {fila['nombre']} desde {request.client.host}")` |
| `app.py` | 185 | `print(f"[DEBUG] error en reportes: {error}")` |

## 6. Alcance y limites del escaneo

- Analisis estatico sobre archivos de texto: no se ejecuta la aplicacion.
- No se prueban exploits ni se hacen peticiones a servidores externos.
- Los patrones son heuristicos: puede haber falsos positivos y, sobre todo, falsos negativos (codigo inseguro escrito de una forma no contemplada).
- Este informe no reemplaza una auditoria humana ni un pentest.

---

Generado por `escaner.py` el 2026-09-26 13:16 usando las reglas de `rules.json`.


<!-- ANEXO-MANUAL -->
## 7. Correcciones aplicadas en app_segura

Esta seccion la escribe el auditor a mano (el escaner no la genera) y mapea cada
hallazgo del informe con su solucion en `app_segura/app.py`. Resultado de
volver a escanear la version corregida:

```bash
python escaner.py app_segura
```

```
 CRITICA : 0
 ALTA    : 0
 MEDIA   : 0
 BAJA    : 0
 TOTAL   : 0
```

| ID | Severidad | Hallazgo | Correccion en app_segura |
|---|---|---|---|
| ARCH-SENS | CRITICA | `.env` versionado en el repositorio | El `.env` **no existe** en la app corregida: solo queda `app_segura/.env.example` con valores vacios e instrucciones de uso. En el despliegue real las variables se cargan del gestor de secretos del hosting. |
| SEC-001 | CRITICA | Clave de API escrita en el codigo | `API_KEY = os.getenv("API_KEY", "")` y `SECRET_KEY = os.getenv("SECRET_JWT", "")`: no hay ningun valor secreto en el archivo. |
| SEC-002 | CRITICA | Credencial de proveedor con formato reconocible | Se elimino la credencial ficticia del codigo. Ademas se documenta en el `.env.example` que hay que **rotar** toda clave que haya estado publicada. |
| SEC-003 | CRITICA | CORS abierto con credenciales | `allow_origins=ORIGENES_PERMITIDOS`, alimentado por la variable `ALLOWED_ORIGINS` (por defecto `http://localhost:3000`), y se mantiene `allow_credentials=True` solo para esa lista. |
| SEC-004 | CRITICA | `eval()` sobre dato del cliente | El endpoint `/calcular` ahora valida la operacion contra la tupla `OPERACIONES_PERMITIDAS` (`sumar`, `restar`, `multiplicar`, `dividir`) y la ejecuta con una funcion propia. No se interpreta codigo. |
| SEC-005 | CRITICA | Secretos con valor real en `.env` | Sin archivo `.env` en la app corregida; los valores viajan por entorno. |
| SEC-006 | ALTA | Contrasena de fabrica en el codigo | `DB_PASSWORD = os.getenv("DB_PASSWORD", "")` y la contrasena del usuario de prueba tambien sale del entorno (`USER_DEMO_PASSWORD`), con valor por defecto sin uso fuera de la demo. |
| SEC-007 | ALTA | Modo debug activado | `DEBUG = os.getenv("DEBUG", "false").lower() == "true"`: apagado por defecto, se enciende solo por entorno. |
| SEC-008 | ALTA | `pickle.loads()` sobre datos recibidos | El endpoint `/config` usa `json.loads`, que no ejecuta codigo al deserializar. |
| SEC-009 | ALTA | Consulta SQL por concatenacion | Consulta parametrizada: `BD.execute("SELECT ... WHERE email = ?", (email,))`. |
| SEC-010 | ALTA | Login sin limite de intentos | Funcion `rate_limit(ip)` en memoria: 5 intentos por minuto y por IP; al superarlos responde **HTTP 429** y deja log del bloqueo. |
| SEC-011 | ALTA | `ALLOWED_HOSTS = ["*"]` | `ALLOWED_HOSTS` viene del entorno y se aplica `TrustedHostMiddleware` de Starlette, que rechaza cualquier host no autorizado. |
| SEC-012 | ALTA | `.env.example` con valores reales | `app_segura/.env.example` deja vacios los secretos y explica como completarlos. |
| SEC-013 | MEDIA | MD5 para contrasenas | `hashlib.pbkdf2_hmac("sha256", ...)` con sal aleatoria de 16 bytes por usuario, 200.000 iteraciones y comparacion con `hmac.compare_digest` (tiempo constante). El docstring aclara que en un proyecto real se usa bcrypt o argon2. |
| SEC-014 | MEDIA | Cookie sin banderas | `set_cookie(..., httponly=True, secure=True, samesite="lax", max_age=1800)`. |
| SEC-015 | MEDIA | Sin headers de seguridad | `CabecerasSeguridadMiddleware` (subclase de `BaseHTTPMiddleware` de Starlette) que agrega `X-Content-Type-Options`, `X-Frame-Options`, `Strict-Transport-Security`, `Referrer-Policy`, `Content-Security-Policy` y `Permissions-Policy` a cada respuesta. |
| SEC-016 | MEDIA | Detalle interno del error al cliente | Las excepciones se registran con `logging` (`logger.error`) y al cliente se le responde un mensaje generico. |
| SEC-017 | MEDIA | TLS sin verificar | `descargar_reporte()` usa `urllib.request.urlopen` con la verificacion de certificado y de hostname por defecto; se elimino el contexto sin verificar. |
| SEC-018 | MEDIA | Metodos y headers CORS abiertos | `allow_methods=["GET", "POST"]` y `allow_headers=["Authorization", "Content-Type"]`. |
| SEC-019 | BAJA | `print()` de depuracion | Reemplazado por el modulo `logging` con niveles (`info`, `warning`, `error`). |

### Cambios adicionales que no detecta el escaner

- El token de sesion paso de ser `base64(email|secreto_fijo)` a estar **firmado con
  HMAC-SHA256 y con vencimiento de 30 minutos**, y `/perfil` valida firma y
  caducidad antes de devolver datos.
- La comparacion de contrasenas usa tiempo constante, para no filtrar informacion
  por diferencia de tiempos de respuesta.
- El rate limit es en memoria: alcanza para una instancia. Con varias instancias
  o varias workers de uvicorn hay que mover el contador a Redis o colocar un WAF.

> Reejecutar `python escaner.py app_vulnerable --reporte hallazgos/INFORME_AUDITORIA.md`
> regenera las secciones 1 a 6 y conserva esta seccion 7 (el escaner respeta el
> marcador `<!-- ANEXO-MANUAL -->`).
