"""
Guardrails (barreras de seguridad) del asistente RAG de Frutolandia.

Este módulo concentra las defensas que rodean al sistema de recuperación y
generación: saneamiento del texto de entrada y de la base de conocimiento,
decisión de relevancia por umbral de similitud y mensaje de rechazo amable para
las consultas que caen fuera del tema de la base.

Es el único módulo que define las constantes de configuración (umbral, top-k,
stopwords y temas), para que construir_indice, responder y evaluar compartan
exactamente la misma lógica de decisión.

Uso:
    from guardrails import relevancia_consulta, mensaje_rechazo, sanear_texto
"""

from __future__ import annotations

import re
import unicodedata

# Umbral de similitud coseno mínimo para aceptar una consulta (configurable por CLI).
UMBRAL_POR_DEFECTO = 0.25

# Cantidad de fragmentos recuperados que se pasan como evidencia a la respuesta.
TOP_K_POR_DEFECTO = 3

# Cantidad mínima de palabras para considerar que una consulta es interpretable.
PALABRAS_MINIMAS = 3

# Stopwords en español (sklearn solo trae inglés): evita que el coseno se
# concentre en palabras funcionales y no en el tema real de la consulta.
STOPWORDS_ES = frozenset(
    {
        "a", "al", "algo", "algunas", "algunos", "ante", "antes", "aquí", "así",
        "cada", "como", "con", "contra", "cuál", "cuáles", "cuándo", "cuánto",
        "cuánta", "cuántos", "de", "del", "desde", "dónde", "dos", "e", "el",
        "ella", "ellas", "ellos", "en", "entre", "era", "es", "esa", "esas",
        "ese", "eso", "esos", "esta", "estaba", "están", "estar", "estas", "este",
        "esto", "estos", "estoy", "fue", "fueron", "ha", "haber", "hasta", "hay",
        "la", "las", "le", "les", "lo", "los", "más", "me", "mi", "mis", "mucho",
        "muy", "nada", "ni", "no", "nos", "nuestra", "nuestro", "o", "otro",
        "para", "pero", "poco", "por", "porque", "que", "quién", "quiénes",
        "se", "sea", "según", "ser", "sí", "sido", "sin", "sobre", "solo", "son",
        "su", "sus", "también", "te", "tiene", "tienen", "todo", "todos", "tu",
        "tus", "un", "una", "uno", "unos", "unas", "usted", "va", "y", "ya",
    }
)

# Etiquetas legibles de los temas cubiertos por la base de conocimiento.
TEMA_POR_FUENTE = {
    "envios-y-entregas.md": "envíos y entregas",
    "productos-y-stock.md": "productos y stock",
    "pagos-y-facturacion.md": "pagos y facturación",
    "devoluciones-y-reclamos.md": "devoluciones y reclamos",
}

# Mensajes del guardrail: texto único, configurable desde este diccionario.
MENSAJES = {
    "rechazo": (
        "Gracias por escribirnos. Tu consulta no coincide con la base de conocimiento "
        "de Frutolandia, así que no te puedo responder con información verificada "
        "(preferimos no inventar). Te puedo ayudar con: {temas}. Si tu consulta es "
        "sobre esos temas, reformulala con más detalle e intento de nuevo."
    ),
    "sin_indice": (
        "Todavía no está construido el índice TF-IDF. Ejecutá primero "
        "'python construir_indice.py' y volvé a probar."
    ),
    "consulta_invalida": (
        "No entendí la consulta. Escribí una pregunta con al menos {palabras} palabras, "
        "por ejemplo: ¿Cuánto tarda el envío a Córdoba?"
    ),
    "error_api": (
        "No se pudo consultar el modelo de lenguaje ({motivo}). Te devuelvo la evidencia "
        "de la base de conocimiento para que la revises."
    ),
}


def sanear_texto(texto: str) -> str:
    """
    Normaliza un texto para vectorizarlo o compararlo.

    Pasa el texto a minúsculas, elimina acentos y signos de puntuación y colapsa
    espacios repetidos. Se aplica igual en la indexación y en la consulta, para
    que ambas queden en el mismo espacio de comparación.
    """
    if not isinstance(texto, str):
        return ""
    sin_acentos = unicodedata.normalize("NFKD", texto.lower())
    sin_acentos = "".join(caracter for caracter in sin_acentos if not unicodedata.combining(caracter))
    sin_puntuacion = re.sub(r"[^a-z0-9\s]", " ", sin_acentos)
    return re.sub(r"\s+", " ", sin_puntuacion).strip()


def es_consulta_valida(consulta: str) -> bool:
    """Indica si la consulta tiene contenido suficiente para ser interpretable."""
    return len(sanear_texto(consulta).split()) >= PALABRAS_MINIMAS


def relevancia_consulta(consulta: str, score: float, umbral: float = UMBRAL_POR_DEFECTO) -> bool:
    """
    Decide si la consulta (o el título de un documento) entra al tema de la base.

    Son dos condiciones: que la consulta sea válida y que su similitud coseno con
    la mejor evidencia supere el umbral. Un score NaN (consulta sin términos del
    vocabulario) también se rechaza.
    """
    if not es_consulta_valida(consulta):
        return False
    return float(score) == float(score) and float(score) >= float(umbral)


def etiqueta_decision(score: float, umbral: float = UMBRAL_POR_DEFECTO) -> str:
    """Devuelve 'aceptada' o 'rechazada' según el score y el umbral configurado."""
    return "aceptada" if float(score) >= float(umbral) else "rechazada"


def temas_conocidos() -> list[str]:
    """Lista los temas cubiertos por la base de conocimiento, en orden estable."""
    return list(TEMA_POR_FUENTE.values())


def mensaje_rechazo(consulta: str | None = None, plantilla: str | None = None) -> str:
    """
    Arma el mensaje de rechazo amable para las consultas fuera de tema.

    Es configurable: se puede pasar otra plantilla o editar `MENSAJES["rechazo"]`
    sin tocar el resto del pipeline.
    """
    texto = plantilla or MENSAJES["rechazo"]
    mensaje = texto.format(
        temas=", ".join(temas_conocidos()),
        consulta=consulta or "",
        palabras=PALABRAS_MINIMAS,
    )
    if consulta:
        mensaje += f'\nConsulta recibida: "{consulta}"'
    return mensaje
