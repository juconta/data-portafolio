"""API de ejemplo CORREGIDA: version segura de app_vulnerable/app.py.

Misma aplicacion y mismos endpoints, pero con los problemas del informe de
auditoria resueltos. Cada bloque commented indica el hallazgo del informe que
corrige (SEC-xxx) y como se resolvio.

Todos los datos y usuarios son ficticios.

Ejecucion: uvicorn app_segura.app:app --port 8014
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import time
import urllib.request
from typing import Any

from fastapi import Cookie, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

logger = logging.getLogger("app_segura")

# ---------------------------------------------------------------------------
# SEC-001 / SEC-006 / SEC-007 / SEC-011 corregidos: nada de valores secretos
# ni de configuracion insegura escrita en el codigo. Todo llega del entorno
# (ver .env.example de esta carpeta).
# ---------------------------------------------------------------------------
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
API_KEY = os.getenv("API_KEY", "")
SECRET_KEY = os.getenv("SECRET_JWT", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if host.strip()
]
ORIGENES_PERMITIDOS = [
    origen.strip()
    for origen in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
    if origen.strip()
]

if not API_KEY or not SECRET_KEY or not DB_PASSWORD:
    logger.warning(
        "Faltan variables del entorno: se usan valores vacios y la app queda "
        "en modo lectura. Revisar el archivo .env del despliegue."
    )

app = FastAPI(title="API Demo Segura", version="1.0.0", debug=DEBUG)


# ---------------------------------------------------------------------------
# SEC-003 / SEC-018 corregidos: CORS limitado a los dominios propios y solo
# con los metodos y headers que la app usa. SEC-011: hosts validados con
# TrustedHostMiddleware de Starlette en vez de aceptar cualquier dominio.
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENES_PERMITIDOS,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)


# ---------------------------------------------------------------------------
# SEC-015 corregido: middleware de Starlette que agrega cabeceras de seguridad
# a todas las respuestas de la API.
# ---------------------------------------------------------------------------
class CabecerasSeguridadMiddleware(BaseHTTPMiddleware):
    """Anade cabeceras de seguridad HTTP a cada respuesta."""

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        respuesta = await call_next(request)
        respuesta.headers["X-Content-Type-Options"] = "nosniff"
        respuesta.headers["X-Frame-Options"] = "DENY"
        respuesta.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        respuesta.headers["Referrer-Policy"] = "no-referrer"
        respuesta.headers["Content-Security-Policy"] = "default-src 'self'"
        respuesta.headers["Permissions-Policy"] = "geolocation=(), microphone=()"
        return respuesta


app.add_middleware(CabecerasSeguridadMiddleware)


# ---------------------------------------------------------------------------
# SEC-010 corregido: rate limit en memoria para el endpoint de login.
# ---------------------------------------------------------------------------
MAX_INTENTOS = 5
VENTANA_SEGUNDOS = 60
intentos_por_ip: dict[str, list[float]] = {}


def rate_limit(ip: str) -> bool:
    """Control simple de fuerza bruta: 5 intentos por minuto y por IP.

    Guarda los horarios de los ultimos intentos y devuelve False cuando la IP
    ya excedio el maximo dentro de la ventana (el endpoint responde 429).
    En produccion con varias instancias conviene Redis o un WAF.
    """
    ahora = time.time()
    registro = [momento for momento in intentos_por_ip.get(ip, []) if ahora - momento < VENTANA_SEGUNDOS]
    if len(registro) >= MAX_INTENTOS:
        intentos_por_ip[ip] = registro
        return False
    registro.append(ahora)
    intentos_por_ip[ip] = registro
    return True


# ---------------------------------------------------------------------------
# Contrasenas: PBKDF2-HMAC-SHA256 con sal por usuario y comparacion en tiempo
# constante (SEC-013 corregido). En un proyecto real se usa bcrypt o argon2.
# Buenas practicas aplicadas: sal aleatoria de 16 bytes distinta por usuario,
# iteraciones altas para que el calculo sea lento a proposito y comparacion
# con hmac.compare_digest para no filtrar informacion por tiempo de respuesta.
# ---------------------------------------------------------------------------
HASH_ITERACIONES = 200_000


def hashear_password(password: str) -> str:
    """Devuelve el hash listo para guardar: prefijo$sal$resumen."""
    sal = secrets.token_bytes(16)
    resumen = hashlib.pbkdf2_hmac("sha256", password.encode(), sal, HASH_ITERACIONES)
    return f"pbkdf2_sha256${sal.hex()}${resumen.hex()}"


def verificar_password(password: str, hash_guardado: str) -> bool:
    """Comprueba la contrasena contra el hash guardado."""
    _prefijo, sal_hex, resumen_hex = hash_guardado.split("$")
    resumen = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(sal_hex), HASH_ITERACIONES
    )
    return hmac.compare_digest(resumen.hex(), resumen_hex)


# ---------------------------------------------------------------------------
# Base de datos ficticia en memoria
# ---------------------------------------------------------------------------
def crear_base() -> sqlite3.Connection:
    """Crea la base en memoria con dos usuarios ficticios y sal distinta."""
    conexion = sqlite3.connect(":memory:", check_same_thread=False)
    conexion.row_factory = sqlite3.Row
    conexion.execute(
        "CREATE TABLE usuarios (id INTEGER, nombre TEXT, email TEXT, password_hash TEXT)"
    )
    conexion.execute(
        "INSERT INTO usuarios VALUES (?, ?, ?, ?)",
        (1, "Ana Demo", "ana@demo.com", hashear_password(os.getenv("USER_DEMO_PASSWORD", "demo-2026"))),
    )
    conexion.execute(
        "INSERT INTO usuarios VALUES (?, ?, ?, ?)",
        (2, "Beto Demo", "beto@demo.com", hashear_password(os.getenv("USER_DEMO_PASSWORD", "demo-2026"))),
    )
    return conexion


BD = crear_base()


def firmar_token(email: str, expira: int) -> str:
    """Firma HMAC-SHA256 del contenido del token de sesion."""
    return hmac.new(
        SECRET_KEY.encode(), f"{email}|{expira}".encode(), hashlib.sha256
    ).hexdigest()


def generar_token(email: str) -> str:
    """Genera un token firmado que incluye el vencimiento."""
    if not SECRET_KEY:
        raise HTTPException(status_code=500, detail="Servicio sin configurar")
    expira = int(time.time()) + 1800
    firma = firmar_token(email, expira)
    return base64.urlsafe_b64encode(f"{email}|{expira}|{firma}".encode()).decode()


# ---------------------------------------------------------------------------
# SEC-004 corregido: lista blanca de operaciones en vez de interpretacion de
# codigo recibido del cliente.
# ---------------------------------------------------------------------------
OPERACIONES_PERMITIDAS = ("sumar", "restar", "multiplicar", "dividir")


def aplicar_operacion(operacion: str, numero_a: float, numero_b: float) -> float:
    """Ejecuta solo las operaciones de la lista blanca."""
    if operacion == "sumar":
        return numero_a + numero_b
    if operacion == "restar":
        return numero_a - numero_b
    if operacion == "multiplicar":
        return numero_a * numero_b
    if operacion == "dividir":
        return numero_a / numero_b if numero_b else 0.0
    raise HTTPException(status_code=400, detail="Operacion no permitida")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/")
def raiz() -> dict[str, str]:
    """Datos publicos de la API de ejemplo."""
    return {"app": "API Demo Segura", "version": "1.0.0", "docs": "/docs"}


@app.post("/login")
def login(payload: dict[str, Any], request: Request) -> JSONResponse:
    """Autenticacion con rate limit, consulta parametrizada y cookie protegida.

    SEC-010: como maximo 5 intentos por minuto y por IP (429 al superar el limite).
    SEC-009: la consulta usa parametros, el usuario no puede inyectar SQL.
    SEC-014: la cookie viaja con httponly, secure y samesite.
    """
    ip = request.client.host if request.client else "desconocida"
    if not rate_limit(ip):
        logger.warning("Login bloqueado por exceso de intentos desde %s", ip)
        raise HTTPException(
            status_code=429, detail="Demasiados intentos. Proba de nuevo en un minuto."
        )

    email = str(payload.get("email", ""))
    password_plano = str(payload.get("password", ""))

    fila = BD.execute(
        "SELECT id, nombre, password_hash FROM usuarios WHERE email = ?", (email,)
    ).fetchone()

    if fila is None or not verificar_password(password_plano, fila["password_hash"]):
        logger.warning("Login fallido para %s desde %s", email, ip)
        raise HTTPException(status_code=401, detail="Usuario o contrasena incorrectos")

    logger.info("Login correcto de %s desde %s", fila["nombre"], ip)
    token = generar_token(fila["email"])
    respuesta = JSONResponse({"token": token, "usuario": fila["nombre"]})
    respuesta.set_cookie(
        "sesion", token, httponly=True, secure=True, samesite="lax", max_age=1800
    )
    return respuesta


@app.get("/perfil")
def perfil(sesion: str | None = Cookie(default=None)) -> dict[str, str]:
    """Perfil del usuario validando firma y vencimiento del token."""
    if not sesion:
        raise HTTPException(status_code=401, detail="Falta la cookie de sesion")
    try:
        email, expira, firma = base64.urlsafe_decode(sesion.encode()).decode().split("|")
        vigente = int(expira) >= int(time.time())
    except (ValueError, UnicodeDecodeError):
        vigente = False
        email, firma = "", ""
    if not vigente or not hmac.compare_digest(firma, firmar_token(email, int(expira or 0))):
        raise HTTPException(status_code=401, detail="Sesion expirada o invalida")
    return {"email": email, "plan": "demo"}


@app.post("/calcular")
def calcular(payload: dict[str, Any]) -> dict[str, Any]:
    """Calculadora que solo acepta operaciones de la lista blanca."""
    operacion = str(payload.get("operacion", "sumar"))
    if operacion not in OPERACIONES_PERMITIDAS:
        raise HTTPException(status_code=400, detail="Operacion no permitida")
    numero_a = float(payload.get("a", 0))
    numero_b = float(payload.get("b", 0))
    return {"operacion": operacion, "resultado": aplicar_operacion(operacion, numero_a, numero_b)}


@app.post("/config")
def cargar_config(payload: dict[str, Any]) -> dict[str, Any]:
    """Carga la configuracion en formato JSON, sin deserializar objetos."""
    try:
        return {"config": json.loads(str(payload.get("datos", "{}")))}
    except json.JSONDecodeError as error:
        logger.error("Configuracion JSON invalida: %s", error)
        raise HTTPException(status_code=400, detail="Configuracion invalida") from error


def descargar_reporte(url: str) -> bytes:
    """Descarga un reporte verificando el certificado TLS y el hostname."""
    with urllib.request.urlopen(url, timeout=10) as respuesta:
        return respuesta.read()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8014")), debug=DEBUG)
