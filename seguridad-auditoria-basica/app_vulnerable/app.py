"""API de ejemplo VULNERABLE: objetivo practico de la auditoria de seguridad.

Este archivo NO debe usarse en produccion. Esta escrito a proposito con los
errores mas comunes que detecta un escaner estatico, y cada uno esta marcado
con un comentario "# VULNERABILIDAD" para poder compararlo, linea por linea,
con la version corregida de app_segura/app.py.

Todos los datos, usuarios, claves y credenciales son ficticios y solo existen
para la demo del informe.

Ejecucion: uvicorn app_vulnerable.app:app --port 8013
"""

from __future__ import annotations

import base64
import hashlib
import os
import pickle
import sqlite3
import ssl
import urllib.request
from typing import Any

from fastapi import Cookie, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# VULNERABILIDAD (SEC-001 / SEC-002 / SEC-006): credenciales reales escritas
# dentro del archivo de codigo. Cualquiera que lea el repositorio las obtiene.
# ---------------------------------------------------------------------------
API_KEY_GLOBAL = "sk_EJEMPLO_REDACTADO_PARA_REPO_PUBLICO"  # VULNERABILIDAD
SECRET_KEY = "clave-de-sesion-supersecreta-2024"  # VULNERABILIDAD
DB_PASSWORD = "admin123"  # VULNERABILIDAD: contrasena de fabrica

# ---------------------------------------------------------------------------
# VULNERABILIDAD (SEC-007 / SEC-011): configuracion abierta y debug prendido.
# ---------------------------------------------------------------------------
DEBUG = True  # VULNERABILIDAD: en produccion muestra trazas internas
ALLOWED_HOSTS = ["*"]  # VULNERABILIDAD: responde en cualquier dominio

app = FastAPI(title="API Demo Vulnerable", version="0.1.0", debug=DEBUG)

# ---------------------------------------------------------------------------
# VULNERABILIDAD (SEC-003 / SEC-018): CORS abierto a todo el mundo, con
# credenciales habilitadas y todos los metodos y headers permitidos.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # VULNERABILIDAD: cualquier sitio web puede llamar la API
    allow_credentials=True,  # VULNERABILIDAD: cookies y cabeceras de auth
    allow_methods=["*"],  # VULNERABILIDAD: cualquier metodo HTTP
    allow_headers=["*"],  # VULNERABILIDAD: cualquier cabecera
)


# ---------------------------------------------------------------------------
# Base de datos ficticia en memoria
# ---------------------------------------------------------------------------
def hashear_password(password: str) -> str:
    """Guarda la contrasena del usuario.

    VULNERABILIDAD (SEC-013): MD5 con un sufijo fijo no es un hash de
    contrasenas; se rompe con facilidad y dos usuarios con la misma
    contrasena generan el mismo valor.
    """
    return hashlib.md5((password + "salt").encode()).hexdigest()


def crear_base() -> sqlite3.Connection:
    """Crea la base en memoria con dos usuarios ficticios."""
    conexion = sqlite3.connect(":memory:", check_same_thread=False)
    conexion.row_factory = sqlite3.Row
    conexion.execute(
        "CREATE TABLE usuarios (id INTEGER, nombre TEXT, email TEXT, password_hash TEXT)"
    )
    conexion.execute(
        "INSERT INTO usuarios VALUES (?, ?, ?, ?)",
        (1, "Ana Demo", "ana@demo.com", hashear_password("admin123")),
    )
    conexion.execute(
        "INSERT INTO usuarios VALUES (?, ?, ?, ?)",
        (2, "Beto Demo", "beto@demo.com", hashear_password("admin123")),
    )
    return conexion


BD = crear_base()


def token_de_sesion(email: str) -> str:
    """Genera un token de sesion.

    VULNERABILIDAD: el token es la direccion de correo en texto plano y usa un
    secreto fijo, asi que es adivinable y no caduca nunca.
    """
    return base64.urlsafe_b64encode(f"{email}|{SECRET_KEY}".encode()).decode()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def raiz() -> dict[str, str]:
    """Datos publicos de la API de ejemplo."""
    return {"app": "API Demo Vulnerable", "version": "0.1.0", "docs": "/docs"}


@app.post("/login")
def login(payload: dict[str, Any], request: Request) -> JSONResponse:
    """Autenticacion de usuarios.

    VULNERABILIDAD (SEC-010): no hay proteccion frente a ataques de fuerza
    bruta, el endpoint acepta cuantas consultas se le envien y no deja
    registro de los fallos.
    """
    email = str(payload.get("email", ""))
    password_plano = str(payload.get("password", ""))

    # VULNERABILIDAD (SEC-009): inyeccion SQL. La consulta se arma pegando el
    # texto del usuario dentro de la cadena, en vez de usar parametros.
    fila = BD.execute(
        f"SELECT id, nombre, password_hash FROM usuarios WHERE email = '{email}'"
    ).fetchone()

    if fila is None or fila["password_hash"] != hashear_password(password_plano):
        print(f"[DEBUG] login fallido para {email} desde {request.client.host}")
        raise HTTPException(status_code=401, detail="Usuario o contrasena incorrectos")

    print(f"[DEBUG] login correcto de {fila['nombre']} desde {request.client.host}")
    respuesta = JSONResponse({"token": token_de_sesion(email), "usuario": fila["nombre"]})

    # VULNERABILIDAD (SEC-014): la cookie de sesion viaja sin cifrar, se puede
    # leer desde JavaScript y no tiene proteccion SameSite.
    respuesta.set_cookie(
        "sesion", token_de_sesion(email), httponly=False, secure=False, samesite="none"
    )
    return respuesta


@app.get("/perfil")
def perfil(sesion: str | None = Cookie(default=None)) -> dict[str, str]:
    """Devuelve los datos del usuario de la cookie de sesion."""
    if not sesion:
        raise HTTPException(status_code=401, detail="Falta la cookie de sesion")
    email = base64.urlsafe_decode(sesion.encode()).decode().split("|")[0]
    return {"email": email, "plan": "demo"}


@app.post("/calcular")
def calcular(payload: dict[str, Any]) -> dict[str, Any]:
    """Calculadora para uso interno.

    VULNERABILIDAD (SEC-004): ejecuta como codigo lo que llega del cliente.
    Con esto, quien llame al endpoint puede correr comandos en el servidor.
    """
    expresion = str(payload.get("expresion", "2+2"))
    return {"resultado": eval(expresion)}  # VULNERABILIDAD


@app.post("/config")
def cargar_config(payload: dict[str, Any]) -> dict[str, Any]:
    """Carga la configuracion serializada del cliente.

    VULNERABILIDAD (SEC-008): deserializar con pickle permite ejecutar codigo
    arbitrario durante la lectura de los datos.
    """
    datos = base64.b64decode(str(payload.get("datos", "")))
    return {"config": pickle.loads(datos)}  # VULNERABILIDAD


@app.get("/reportes")
def listar_reportes() -> JSONResponse:
    """Genera el reporte de ventas del mes.

    VULNERABILIDAD (SEC-016): si algo falla, al cliente se le devuelve el
    mensaje crudo de la excepcion, que revela nombres de tablas, rutas del
    servidor y versiones de librerias.
    """
    try:
        filas = BD.execute("SELECT COUNT(*) AS total FROM usuarios").fetchone()
        return JSONResponse({"total_usuarios": filas["total"]})
    except sqlite3.Error as error:
        print(f"[DEBUG] error en reportes: {error}")
        raise HTTPException(status_code=500, detail=str(error))


def descargar_reporte(url: str) -> bytes:
    """Descarga un reporte desde el servicio externo de la empresa.

    VULNERABILIDAD (SEC-017): se acepta cualquier certificado TLS, con lo que
    un atacante en la red puede leer o modificar el trafico.
    """
    contexto = ssl._create_unverified_context()  # VULNERABILIDAD
    with urllib.request.urlopen(url, context=contexto, timeout=10) as respuesta:
        return respuesta.read()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8013")),
        debug=DEBUG,  # VULNERABILIDAD: el servidor de desarrollo tambien
    )
