"""
Asistente de FAQ por recuperacion de texto (sin LLM).

Responde consultas de clientes sobre la tienda ficticia CasaMuebles usando
un indice de preguntas frecuentes (``data/faq.json``) y *scoring* por
coincidencia de terminos con stemming liviano, implementado solo con la
biblioteca estandar de Python (``re``, ``json``, ``unicodedata``, ``difflib``).

El modulo es deliberadamente liviano (sin pandas / scikit-learn / numpy) para
que el deploy sea minimo: basta con ``fastapi`` + ``uvicorn``.

Uso:
    from chatbot import AsistenteFAQ
    asistente = AsistenteFAQ()
    asistente.responder("Hacen envios a todo el pais?")
"""

from __future__ import annotations

import difflib
import json
import math
import re
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent
RUTA_FAQ = BASE / "data" / "faq.json"

# Confianza minima para considerar que la consulta es relevante al tema.
# Por debajo de este valor se dispara el guardrail de "fuera de tema".
UMBRAL_CONFIANZA = 0.30

# Un unico termino coincidente es evidencia debil: se penaliza el score para
# que preguntas cortas y genericas ("cuanto esta el dolar?") no hacen match.
PENALIDAD_UN_SOLO_MATCH = 0.45

# Umbral de similitud difusa (0-1) para aceptar una coincidencia aproximada.
UMBRAL_SIMILITUD = 0.85

# Mensajes del guardrail cuando la consulta no matchea el FAQ.
MENSAJES_FUERA_DE_TEMA = [
    "Gracias por escribirnos. Tu consulta no parece estar relacionada con nuestro catalogo de muebles, envios o pagos. Para poder ayudarte te puedo responder sobre: envios, costos, garantia, materiales, devoluciones, formas de pago, armado de muebles, colores y tapizados, muebles a medida, rastreo de pedidos o nuestro showroom.",
    "Perdon, todavia no tengo informacion sobre eso. Como soy el asistente de CasaMuebles, lo mejor es consultarme por envios, garantia, materiales, devoluciones, formas de pago o armado de muebles. Si preferis hablar con una persona, podes usar el formulario de contacto de esta pagina.",
]

# Palabras vacias / verbos demasiado genericos: se filtran de la consulta.
STOPWORDS = {
    "a", "al", "algo", "ante", "antes", "aqui", "asi", "ay", "cada", "como",
    "con", "contra", "cual", "cuando", "de", "del", "desde", "donde", "dos",
    "el", "ella", "ellos", "en", "entre", "era", "es", "esa", "ese", "eso",
    "esta", "estoy", "fue", "fui", "ha", "hasta", "hay", "la", "las", "le",
    "les", "lo", "los", "mas", "me", "mi", "mis", "mucho", "muy", "nada",
    "ni", "no", "nos", "o", "otro", "para", "pero", "poco", "por", "porque",
    "que", "quien", "se", "sea", "segun", "ser", "si", "sido", "sin", "sobre",
    "solo", "son", "su", "sus", "tambien", "te", "ten", "tiene", "tienen",
    "toda", "todo", "todos", "tu", "tus", "un", "una", "uno", "y", "ya",
    "hola", "buen", "buenas", "buenos", "dias", "gracias", "favor", "quisiera",
    "necesito", "quiero", "saber", "querria", "queria", "holis", "estar",
}

# Sufijos para el "stemming liviano" (no es Porter: solo recorta la variacion
# morfologica mas comun — plurales, genero, diminutivos y terminaciones verbales).
SUFIJOS = (
    "amiento", "imiento", "aciones", "ucion", "siones", "cion", "ciones",
    "mente", "ados", "adas", "idos", "idas", "ando", "iendo", "ador", "adora",
    "aron", "eron", "aban", "iran", "aria", "eria", "ar", "er", "ir",
    "as", "es", "os", "a", "o", "e", "s",
)


def normalizar(texto: str) -> str:
    """Pasa un texto a minusculas y le quita tildes para comparar tokens."""
    texto = texto.lower().strip()
    descompuesto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def raiz(palabra: str) -> str:
    """Aplica stemming liviano recortando sufijos morfologicos comunes."""
    palabra = normalizar(palabra)
    if len(palabra) <= 4:
        return palabra
    for sufijo in SUFIJOS:
        if palabra.endswith(sufijo) and len(palabra) - len(sufijo) >= 4:
            return palabra[: -len(sufijo)]
    return palabra


def tokenizar(texto: str, quitar_stopwords: bool = True) -> list[str]:
    """Normaliza, divide en tokens, quita stopwords y reduce cada uno a su raiz."""
    limpio = normalizar(texto)
    tokens = re.findall(r"[a-z0-9]+", limpio)
    if quitar_stopwords:
        tokens = [t for t in tokens if t not in STOPWORDS and len(t) > 2]
    return [raiz(t) for t in tokens]


class AsistenteFAQ:
    """
    Asistente de preguntas frecuentes basado en recuperacion por terminos.

    Carga el FAQ, preprocesa cada entrada (pregunta + keywords) y ante una
    consulta puntua cada documento con:

    1. **IDF** — los terminos raros en el corpus pesan mas ("madera" pesa mas
       que "cuanto"), de modo que las palabras genericas no dominan el score.
    2. **Stemming liviano + similitud difusa** — "limpiar"/"limpieza" y
       "sillon"/"sillones" colapsan al mismo termino.
    3. **Penalidad por un solo match** — una unica coincidencia no es
       evidencia suficiente para dar una respuesta.

    Si el mejor score supera ``UMBRAL_CONFIANZA`` devuelve la respuesta del FAQ;
    en caso contrario activa el guardrail de fuera de tema.
    """

    def __init__(self, ruta_faq: Path | str = RUTA_FAQ, umbral: float = UMBRAL_CONFIANZA) -> None:
        """Inicializa el asistente cargando e indexando el FAQ desde disco."""
        self.ruta_faq = Path(ruta_faq)
        self.umbral = umbral
        self.empresa: str = "CasaMuebles"
        self.documentos: list[dict] = []
        self._cargar()
        self._calcular_pesos()

    def _cargar(self) -> None:
        """Lee ``faq.json`` y construye el indice de documentos tokenizados."""
        datos = json.loads(self.ruta_faq.read_text(encoding="utf-8"))
        self.empresa = datos.get("empresa", self.empresa)
        for item in datos["preguntas"]:
            keywords = item.get("keywords", [])
            # El documento indexado es la union de pregunta + keywords, para que
            # el usuario no tenga que usar las palabras exactas del FAQ.
            documento = item["pregunta"] + " " + " ".join(keywords)
            self.documentos.append(
                {
                    "pregunta": item["pregunta"],
                    "respuesta": item["respuesta"],
                    "tokens_pregunta": set(tokenizar(item["pregunta"])),
                    "tokens_documento": set(tokenizar(documento)),
                }
            )

    def _calcular_pesos(self) -> None:
        """Calcula el peso IDF de cada raiz de termino en el corpus del FAQ."""
        total = len(self.documentos)
        self.peso_idf: dict[str, float] = {}
        for termino in {t for doc in self.documentos for t in doc["tokens_documento"]}:
            documentos_con_termino = sum(1 for doc in self.documentos if termino in doc["tokens_documento"])
            # IDF de una variante suavizada (BM25 sin longitud): los terminos
            # que no aparecen en ningun documento (df=0) pesan mas, que es
            # justo lo que hace que una consulta fuera de tema se penalice.
            self.peso_idf[termino] = math.log((total + 1) / (documentos_con_termino + 1)) + 1.0

    def _peso(self, termino: str) -> float:
        """Devuelve el peso IDF de un termino (maximo si esta fuera del corpus)."""
        if termino in self.peso_idf:
            return self.peso_idf[termino]
        df0 = math.log((len(self.documentos) + 1) / 1) + 1.0
        return df0

    def _coincidir(self, termino: str, tokens_doc: set[str]) -> float:
        """
        Devuelve el peso de la coincidencia de un termino contra un documento.

        - 1.0 si la raiz coincide exactamente.
        - 0.7 si coincide de forma difusa (similitud >= ``UMBRAL_SIMILITUD``).
        - 0.0 si no hay coincidencia.
        """
        if termino in tokens_doc:
            return 1.0
        mejor = difflib.get_close_matches(termino, tokens_doc, n=1, cutoff=UMBRAL_SIMILITUD)
        if mejor:
            similitud = difflib.SequenceMatcher(None, termino, mejor[0]).ratio()
            return 0.7 * similitud
        return 0.0

    def _score(self, tokens_usuario: list[str], documento: dict) -> float:
        """
        Puntua un documento combinando cobertura de la consulta y del documento.

        - 70% cobertura ponderada de la consulta (que fraccion de lo que el
          usuario pregunto encontramos en el FAQ).
        - 30% cobertura ponderada del documento (precision: no matcheamos con
          un documento gigante que menciona 200 palabras).
        """
        if not tokens_usuario:
            return 0.0

        tokens_doc = documento["tokens_documento"]
        tokens_pregunta = documento["tokens_pregunta"]

        peso_consulta_total = sum(self._peso(t) for t in tokens_usuario)
        if peso_consulta_total == 0:
            return 0.0

        peso_doc_total = sum(self.peso_idf.get(t, 1.0) for t in tokens_doc) or 1.0

        match_consulta = 0.0
        match_pregunta = 0.0
        matches = 0
        for termino in tokens_usuario:
            fuerza = self._coincidir(termino, tokens_doc)
            if fuerza > 0:
                matches += 1
                match_consulta += self._peso(termino) * fuerza
                if self._coincidir(termino, tokens_pregunta) > 0:
                    match_pregunta += self._peso(termino) * fuerza

        if matches == 0:
            return 0.0

        cobertura_consulta = match_consulta / peso_consulta_total
        cobertura_pregunta = match_pregunta / peso_doc_total
        score = 0.7 * cobertura_consulta + 0.3 * min(cobertura_pregunta, 1.0)

        # Evidencia debil: una sola palabra en comun no alcanza para responder.
        if matches == 1 and len(set(tokens_usuario)) > 1:
            score *= PENALIDAD_UN_SOLO_MATCH

        return min(score, 1.0)

    def responder(self, mensaje: str) -> dict:
        """
        Responde una consulta del usuario.

        Returns:
            dict con las claves ``respuesta``, ``confianza``, ``relevante`` y
            ``pregunta_match`` (la pregunta del FAQ que gano, o ``None``).
        """
        tokens = tokenizar(mensaje or "")

        if not tokens:
            return {
                "respuesta": MENSAJES_FUERA_DE_TEMA[1],
                "confianza": 0.0,
                "relevante": False,
                "pregunta_match": None,
            }

        puntajes = [(self._score(tokens, doc), doc) for doc in self.documentos]
        puntajes.sort(key=lambda par: par[0], reverse=True)
        mejor_score, mejor_doc = puntajes[0]

        # Guardrail: por debajo del umbral la consulta se considera fuera de tema.
        if mejor_score < self.umbral:
            # Rotacion simple (determinista segun el largo del mensaje) para que
            # el bot no responda siempre exactamente lo mismo.
            idx = len(mensaje.strip()) % len(MENSAJES_FUERA_DE_TEMA)
            return {
                "respuesta": MENSAJES_FUERA_DE_TEMA[idx],
                "confianza": round(mejor_score, 3),
                "relevante": False,
                "pregunta_match": None,
            }

        return {
            "respuesta": mejor_doc["respuesta"],
            "confianza": round(mejor_score, 3),
            "relevante": True,
            "pregunta_match": mejor_doc["pregunta"],
        }

    def ejemplos(self) -> list[dict]:
        """Devuelve el catalogo de preguntas del FAQ (para el frontend)."""
        return [{"pregunta": doc["pregunta"]} for doc in self.documentos]


if __name__ == "__main__":  # pragma: no cover - demo manual
    bot = AsistenteFAQ()
    for consulta in [
        "Hacen envios a todo el pais?",
        "quiero devolver un sillon",
        "aceptan transferencia?",
        "como armo una pizza",
    ]:
        r = bot.responder(consulta)
        print(f"\nUsuario: {consulta}")
        print(f"Bot    : {r['respuesta']}")
        print(f"        confianza={r['confianza']} relevante={r['relevante']}")
