"""
Construcción del índice TF-IDF de la base de conocimiento de Frutolandia.

Lee los documentos Markdown de `datos/conocimiento/`, los parte en fragmentos de
tipo pregunta/respuesta, entrena un vectorizador TF-IDF y persiste el índice y el
vectorizador con joblib para que `responder.py` y `evaluar.py` los reutilicen sin
volver a entrenar.

El pipeline es 100 % local: no depende de ninguna API ni de embeddings externos.

Uso:
    python construir_indice.py
"""

from __future__ import annotations

import re
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer

from guardrails import STOPWORDS_ES, sanear_texto

BASE = Path(__file__).resolve().parent
CARPETA_CONOCIMIENTO = BASE / "datos" / "conocimiento"
RUTA_INDICE = BASE / "datos" / "indice_tfidf.pkl"
RUTA_VECTORIZADOR = BASE / "datos" / "vectorizador.pkl"

# Formato esperado de cada fragmento: "- **¿Pregunta?** Respuesta"
PATRON_FRAGMENTO = re.compile(r"^-\s*\*\*(?P<titulo>.+?)\*\*\s*(?P<respuesta>.*)$")

# Las stopwords van sin acentos: el texto ya pasa por `sanear_texto`, así que el
# tokenizador nunca genera "cuál" ni "más" (evita el warning de sklearn).
STOPWORDS_INDEXABLES = sorted({sanear_texto(palabra) for palabra in STOPWORDS_ES})


def parsear_documento(ruta: Path) -> list[dict]:
    """
    Convierte un Markdown de la base de conocimiento en fragmentos indexables.

    Cada bullet `- **titulo** respuesta` es un fragmento independiente (indexa
    mucho mejor que el documento entero) y las líneas de continuación del bullet
    se anexan a su respuesta.
    """
    fragmentos: list[dict] = []
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        coincidencia = PATRON_FRAGMENTO.match(linea.strip())
        if coincidencia:
            fragmentos.append(
                {
                    "id": f"{ruta.stem}#{len(fragmentos) + 1}",
                    "fuente": ruta.name,
                    "seccion": ruta.stem.replace("-", " "),
                    "titulo": coincidencia.group("titulo").strip(),
                    "respuesta": coincidencia.group("respuesta").strip(),
                }
            )
        elif fragmentos and linea.startswith((" ", "\t")) and linea.strip():
            fragmentos[-1]["respuesta"] = f"{fragmentos[-1]['respuesta']} {linea.strip()}".strip()
    for fragmento in fragmentos:
        fragmento["respuesta"] = re.sub(r"\s+", " ", fragmento["respuesta"]).strip()
        fragmento["texto"] = sanear_texto(f"{fragmento['titulo']} {fragmento['respuesta']}")
    return fragmentos


def cargar_fragmentos() -> list[dict]:
    """Lee todos los Markdown de la base de conocimiento y devuelve sus fragmentos."""
    archivos = sorted(CARPETA_CONOCIMIENTO.glob("*.md"))
    if not archivos:
        raise FileNotFoundError(f"No hay documentos en {CARPETA_CONOCIMIENTO}")
    fragmentos = [fragmento for ruta in archivos for fragmento in parsear_documento(ruta)]
    if not fragmentos:
        raise ValueError("Los documentos no contienen fragmentos con el formato - **pregunta** respuesta")
    return fragmentos


def construir_indice(fragmentos: list[dict]) -> tuple[dict, TfidfVectorizer]:
    """
    Entrena el vectorizador TF-IDF y arma el índice de fragmentos.

    Usa unigramas y bigramas con TF sublineal: los bigramas ("pago rechazado",
    "sin gluten") son justamente los que aparecen en las preguntas reales.
    """
    vectorizador = TfidfVectorizer(
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        sublinear_tf=True,
        min_df=1,
        stop_words=STOPWORDS_INDEXABLES,
        token_pattern=r"(?u)\b\w\w+\b",
    )
    matriz = vectorizador.fit_transform([fragmento["texto"] for fragmento in fragmentos])
    indice = {
        "documentos": fragmentos,
        "matriz": matriz,
        "config": {
            "ngram_range": (1, 2),
            "sublinear_tf": True,
            "stopwords_es": len(STOPWORDS_ES),
            "fragmentos": len(fragmentos),
        },
    }
    return indice, vectorizador


def guardar_indice(indice: dict, vectorizador: TfidfVectorizer) -> None:
    """Persiste el índice y el vectorizador con joblib en `datos/`."""
    RUTA_INDICE.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(indice, RUTA_INDICE)
    joblib.dump(vectorizador, RUTA_VECTORIZADOR)


def cargar_indice() -> tuple[dict, TfidfVectorizer]:
    """Carga el índice y el vectorizador persistidos."""
    if not RUTA_INDICE.exists() or not RUTA_VECTORIZADOR.exists():
        raise FileNotFoundError("Falta el índice TF-IDF: ejecuta 'python construir_indice.py'")
    return joblib.load(RUTA_INDICE), joblib.load(RUTA_VECTORIZADOR)


def main() -> None:
    fragmentos = cargar_fragmentos()
    indice, vectorizador = construir_indice(fragmentos)
    guardar_indice(indice, vectorizador)

    por_fuente: dict[str, int] = {}
    for fragmento in fragmentos:
        por_fuente[fragmento["fuente"]] = por_fuente.get(fragmento["fuente"], 0) + 1

    print("=== Índice TF-IDF construido ===")
    for fuente, cantidad in sorted(por_fuente.items()):
        print(f"  {fuente:<28} {cantidad:>3} fragmentos")
    print(f"  {'total':<28} {len(fragmentos):>3} fragmentos")
    print(f"  matriz TF-IDF: {indice['matriz'].shape[0]} docs x {indice['matriz'].shape[1]} términos")
    print(f"  términos no nulos: {indice['matriz'].nnz}")
    print(f"  índice guardado en {RUTA_INDICE.relative_to(BASE)}")
    print(f"  vectorizador guardado en {RUTA_VECTORIZADOR.relative_to(BASE)}")


if __name__ == "__main__":
    main()
