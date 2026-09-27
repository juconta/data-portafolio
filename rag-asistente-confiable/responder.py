"""
Asistente RAG de Frutolandia: consulta la base de conocimiento y responde.

Recupera los 3 fragmentos más similares (TF-IDF + coseno) y aplica el guardrail
de relevancia: si la similitud no supera el umbral, rechaza la consulta con un
mensaje amable en vez de inventar una respuesta. Si existe la variable de entorno
OPENAI_API_KEY, arma la respuesta con un modelo de chat; si no existe, devuelve
la mejor evidencia de la base de conocimiento. En ambos casos el sistema
funciona sin ninguna API externa.

Uso:
    python responder.py "¿Cuánto tarda el envío a Córdoba?"
    python responder.py "¿Cómo hago una pizza casera?"
    python responder.py "¿Emiten factura?" --umbral 0.3 --top-k 5
"""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

from construir_indice import cargar_indice
from guardrails import (
    MENSAJES,
    TOP_K_POR_DEFECTO,
    UMBRAL_POR_DEFECTO,
    etiqueta_decision,
    mensaje_rechazo,
    relevancia_consulta,
    sanear_texto,
)

BASE = Path(__file__).resolve().parent
OUTPUTS = BASE / "outputs"

URL_CHAT = "https://api.openai.com/v1/chat/completions"
VAR_API_KEY = "OPENAI_API_KEY"
MODELO_POR_DEFECTO = "gpt-4o-mini"
TEMPERATURA = 0.2
TIMEOUT_SEGUNDOS = 30
ENCABEZADO_LOG = ["fecha", "pregunta", "umbral", "score_top1", "decision", "modo", "archivo"]


def buscar(consulta: str, indice: dict, vectorizador, top_k: int = TOP_K_POR_DEFECTO) -> list[dict]:
    """
    Recupera los `top_k` fragmentos más similares a la consulta.

    Usa el producto punto entre la matriz TF-IDF del índice y el vector de la
    consulta: como las filas están normalizadas, ese producto es el coseno.
    """
    documentos = indice["documentos"]
    if not documentos:
        return []
    vector = vectorizador.transform([sanear_texto(consulta)])
    scores = (indice["matriz"] @ vector.T).toarray().ravel()
    orden = scores.argsort()[::-1][: max(1, top_k)]
    return [{**documentos[pos], "score": float(scores[pos])} for pos in orden]


def construir_contexto(evidencias: list[dict]) -> str:
    """Arma el contexto con los fragmentos recuperados para mandarlo al modelo."""
    bloques = [
        f"[{indice + 1}] Fuente: {evidencia['fuente']}\n"
        f"Pregunta frecuente: {evidencia['titulo']}\n"
        f"Respuesta oficial: {evidencia['respuesta']}"
        for indice, evidencia in enumerate(evidencias)
    ]
    return "\n\n".join(bloques)


def formatear_evidencias(evidencias: list[dict]) -> str:
    """Presenta la evidencia recuperada como respuesta cuando no hay modelo de lenguaje."""
    partes = ["La base de conocimiento de Frutolandia dice:"]
    for indice, evidencia in enumerate(evidencias, start=1):
        partes.append(
            f"{indice}. {evidencia['titulo']} {evidencia['respuesta']} "
            f"(similitud {evidencia['score']:.3f} · {evidencia['fuente']})"
        )
    return "\n".join(partes)


def generar_respuesta_api(pregunta: str, evidencias: list[dict], modelo: str) -> str | None:
    """
    Genera la respuesta con la API de chat si hay OPENAI_API_KEY configurada.

    Devuelve None si no hay clave o si la llamada falla (timeout, error de red o
    de estado), de modo que el asistente cae en la evidencia local y nunca queda
    sin respuesta. La clave solo viaja en el encabezado de autorización.
    """
    api_key = os.environ.get(VAR_API_KEY, "").strip()
    if not api_key:
        return None

    carga = {
        "model": modelo,
        "temperature": TEMPERATURA,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Sos el asistente de Frutolandia, una frutería online. Respondés en "
                    "español rioplatense, en máximo 4 frases, usando solo la información del "
                    "contexto. Si el contexto no alcanza, decís que no tenés ese dato y "
                    "sugerís contactar al equipo."
                ),
            },
            {
                "role": "user",
                "content": f"Contexto:\n{construir_contexto(evidencias)}\n\nPregunta: {pregunta}",
            },
        ],
    }
    try:
        respuesta = requests.post(
            URL_CHAT,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=carga,
            timeout=TIMEOUT_SEGUNDOS,
        )
        respuesta.raise_for_status()
        return respuesta.json()["choices"][0]["message"]["content"].strip()
    except (requests.RequestException, KeyError, IndexError, ValueError) as error:
        print(f"[aviso] {MENSAJES['error_api'].format(motivo=type(error).__name__)}")
        return None


def guardar_salida(pregunta: str, umbral: float, resultado: dict, evidencias: list[dict]) -> Path:
    """Guarda la respuesta en outputs/ como Markdown y la agrega al registro CSV."""
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    palabras = "-".join(sanear_texto(pregunta).split()[:5]) or "consulta"
    archivo = OUTPUTS / f"respuesta_{palabras}_{marca}.md"

    lineas = [
        "# Consulta al asistente RAG de Frutolandia",
        "",
        f"- **Fecha:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- **Pregunta:** {pregunta}",
        f"- **Umbral de relevancia:** {umbral}",
        f"- **Similitud de la mejor evidencia:** {resultado['score']:.3f}",
        f"- **Guardrail:** {resultado['decision']}",
        f"- **Modo de respuesta:** {resultado['modo']}",
        "",
        "## Respuesta",
        "",
        resultado["respuesta"],
        "",
        f"## Evidencia recuperada (top-{len(evidencias)})",
        "",
    ]
    for indice, evidencia in enumerate(evidencias, start=1):
        lineas.append(
            f"{indice}. **{evidencia['titulo']}** {evidencia['respuesta']} "
            f"— similitud {evidencia['score']:.3f} (`{evidencia['fuente']}`)"
        )
    archivo.write_text("\n".join(lineas) + "\n", encoding="utf-8")

    registro = OUTPUTS / "registro_respuestas.csv"
    fila = pd.DataFrame(
        [
            {
                "fecha": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "pregunta": pregunta,
                "umbral": umbral,
                "score_top1": round(resultado["score"], 4),
                "decision": resultado["decision"],
                "modo": resultado["modo"],
                "archivo": archivo.name,
            }
        ],
        columns=ENCABEZADO_LOG,
    )
    fila.to_csv(registro, sep=";", index=False, mode="a", header=not registro.exists(), encoding="utf-8")
    return archivo


def responder(
    pregunta: str,
    umbral: float = UMBRAL_POR_DEFECTO,
    top_k: int = TOP_K_POR_DEFECTO,
    modelo: str = MODELO_POR_DEFECTO,
) -> dict:
    """
    Ejecuta el flujo completo: recuperar, filtrar con el guardrail y responder.

    Devuelve un diccionario con la decisión, la respuesta, las evidencias
    recuperadas y el modo usado ("api", "evidencia" o "rechazo").
    """
    indice, vectorizador = cargar_indice()
    evidencias = buscar(pregunta, indice, vectorizador, top_k)
    score = evidencias[0]["score"] if evidencias else 0.0

    if not relevancia_consulta(pregunta, score, umbral):
        return {
            "decision": etiqueta_decision(score, umbral),
            "score": score,
            "respuesta": mensaje_rechazo(pregunta),
            "evidencias": evidencias,
            "modo": "rechazo",
        }

    respuesta_api = generar_respuesta_api(pregunta, evidencias, modelo)
    return {
        "decision": "aceptada",
        "score": score,
        "respuesta": respuesta_api or formatear_evidencias(evidencias),
        "evidencias": evidencias,
        "modo": "api" if respuesta_api else "evidencia",
    }


def parsear_argumentos() -> argparse.Namespace:
    """Define los argumentos de la CLI: pregunta, umbral, top-k y modelo."""
    parser = argparse.ArgumentParser(
        description="Consulta la base de conocimiento de Frutolandia con un asistente RAG local."
    )
    parser.add_argument("pregunta", help="Pregunta en lenguaje natural, entre comillas.")
    parser.add_argument(
        "--umbral",
        type=float,
        default=UMBRAL_POR_DEFECTO,
        help=f"Similitud mínima para aceptar la consulta (default: {UMBRAL_POR_DEFECTO}).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=TOP_K_POR_DEFECTO,
        help=f"Cantidad de fragmentos recuperados (default: {TOP_K_POR_DEFECTO}).",
    )
    parser.add_argument(
        "--modelo",
        default=MODELO_POR_DEFECTO,
        help=f"Modelo de chat de OpenAI (default: {MODELO_POR_DEFECTO}).",
    )
    return parser.parse_args()


def main() -> None:
    argumentos = parsear_argumentos()
    try:
        resultado = responder(argumentos.pregunta, argumentos.umbral, argumentos.top_k, argumentos.modelo)
    except FileNotFoundError as error:
        print(f"[error] {error}")
        return

    print(f"Pregunta: {argumentos.pregunta}")
    print(f"Similitud top-1: {resultado['score']:.3f} (umbral {argumentos.umbral})")
    print(f"Guardrail: {resultado['decision']}  |  Modo: {resultado['modo']}")
    print("\n--- Respuesta ---")
    print(resultado["respuesta"])
    if resultado["modo"] != "rechazo":
        print("\n--- Evidencia recuperada ---")
        for indice, evidencia in enumerate(resultado["evidencias"], start=1):
            print(f"{indice}. [{evidencia['score']:.3f}] {evidencia['titulo']} ({evidencia['fuente']})")

    archivo = guardar_salida(argumentos.pregunta, argumentos.umbral, resultado, resultado["evidencias"])
    print(f"\n[ok] Respuesta guardada en {archivo.relative_to(BASE)}")


if __name__ == "__main__":
    main()
