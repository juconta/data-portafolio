"""
CasaMuebles - sitio web con integracion de asistente de IA (GIG 3).

Backend FastAPI que:
  1. Sirve el frontend estatico responsive (hero + chat + contacto).
  2. Expone ``POST /api/chat`` -> asistente de FAQ por recuperacion de texto
     (ver ``chatbot.py``, sin dependencias de LLM).
  3. Expone ``POST /api/contacto`` -> guarda consultas en SQLite validando
     email y descartando spam mediante un campo trampa ('categoria').

Uso:
    uvicorn app:app --port 8000
"""

from __future__ import annotations

import re
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from chatbot import AsistenteFAQ

BASE = Path(__file__).resolve().parent
STATIC_DIR = BASE / "static"
DATA_DIR = BASE / "data"
DB_PATH = DATA_DIR / "mensajes.db"

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
SPAM_CAMPO = "categoria"  # campo trampa: los humanos no lo llenan, los bots si

app = FastAPI(
    title="CasaMuebles - Web con Integracion de IA",
    description="Sitio web con asistente de FAQ por recuperacion de texto y formulario de contacto.",
    version="1.0.0",
)

asistente = AsistenteFAQ()


# --------------------------------------------------------------------------- #
# Modelos de request
# --------------------------------------------------------------------------- #
class MensajeChat(BaseModel):
    """Payload de ``POST /api/chat``."""

    message: str = Field(..., min_length=1, max_length=500, description="Consulta del usuario")


class MensajeContacto(BaseModel):
    """Payload de ``POST /api/contacto`` (incluye el campo trampa anti-spam)."""

    nombre: str = Field(..., min_length=2, max_length=80)
    email: str = Field(..., min_length=5, max_length=120)
    mensaje: str = Field(..., min_length=10, max_length=1000)
    categoria: str = Field("", max_length=80, description="Campo trampa anti-spam (debe ir vacio)")


# --------------------------------------------------------------------------- #
# Base de datos
# --------------------------------------------------------------------------- #
def init_db() -> None:
    """Crea ``data/mensajes.db`` y la tabla ``mensajes`` si no existen."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB_PATH)) as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS mensajes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre     TEXT    NOT NULL,
                email      TEXT    NOT NULL,
                mensaje    TEXT    NOT NULL,
                creado_en  TEXT    NOT NULL
            )
            """
        )
        con.commit()


def guardar_mensaje(nombre: str, email: str, mensaje: str) -> int:
    """Inserta un contacto validado en SQLite y devuelve el id generado."""
    creado = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.execute(
            "INSERT INTO mensajes (nombre, email, mensaje, creado_en) VALUES (?, ?, ?, ?)",
            (nombre.strip(), email.strip().lower(), mensaje.strip(), creado),
        )
        con.commit()
        return int(cur.lastrowid)


init_db()


# --------------------------------------------------------------------------- #
# Frontend estatico
# --------------------------------------------------------------------------- #
@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    """Devuelve la landing page (hero + chat + formulario de contacto)."""
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/salud")
def salud() -> dict:
    """Health check: confirma que la API y el asistente estan levantados."""
    return {
        "estado": "ok",
        "empresa": asistente.empresa,
        "preguntas_cargadas": len(asistente.documentos),
    }


@app.get("/api/faq")
def listar_faq() -> dict:
    """Devuelve la lista de preguntas frecuentes para las sugerencias del chat."""
    return {"preguntas": asistente.ejemplos()}


# --------------------------------------------------------------------------- #
# API del asistente de IA
# --------------------------------------------------------------------------- #
@app.post("/api/chat")
def chat(payload: MensajeChat) -> dict:
    """
    Responde una consulta con el asistente de FAQ.

    Si la confianza del retrieval queda por debajo del umbral, el guardrail
    devuelve una respuesta de "fuera de tema" con sugerencias y ``relevante: false``.
    """
    texto = payload.message.strip()
    if not texto:
        raise HTTPException(status_code=400, detail="El mensaje no puede estar vacio.")

    resultado = asistente.responder(texto)
    return {
        "respuesta": resultado["respuesta"],
        "confianza": resultado["confianza"],
        "relevante": resultado["relevante"],
        "pregunta_match": resultado["pregunta_match"],
    }


# --------------------------------------------------------------------------- #
# API de contacto
# --------------------------------------------------------------------------- #
@app.post("/api/contacto")
def contacto(payload: MensajeContacto) -> JSONResponse:
    """
    Valida y persiste un mensaje de contacto en ``data/mensajes.db``.

    Validaciones: longitud minima de nombre y mensaje, formato de email y
    campo trampa anti-spam (``categoria`` debe venir vacio).
    """
    if not EMAIL_RE.match(payload.email.strip()):
        raise HTTPException(status_code=422, detail="El email no tiene un formato valido.")

    if payload.categoria.strip():
        # Campo trampa: si viene relleno, es un bot. Se responde OK pero no se guarda.
        return JSONResponse(
            status_code=200,
            content={"ok": True, "id": None, "mensaje": "Consulta recibida. Te contactamos dentro de las 48 horas habiles."},
        )

    try:
        id_mensaje = guardar_mensaje(payload.nombre, payload.email, payload.mensaje)
    except sqlite3.Error as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=f"No se pudo guardar el mensaje: {exc}") from exc

    return JSONResponse(
        status_code=201,
        content={
            "ok": True,
            "id": id_mensaje,
            "mensaje": "Consulta recibida. Te contactamos dentro de las 48 horas habiles.",
        },
    )


@app.get("/api/mensajes", include_in_schema=False)
def listar_mensajes() -> dict:
    """Lista los contactos guardados (util para la demo y la verificacion)."""
    with closing(sqlite3.connect(DB_PATH)) as con:
        con.row_factory = sqlite3.Row
        filas = con.execute(
            "SELECT id, nombre, email, mensaje, creado_en FROM mensajes ORDER BY id DESC"
        ).fetchall()
    return {"total": len(filas), "mensajes": [dict(f) for f in filas]}


app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
