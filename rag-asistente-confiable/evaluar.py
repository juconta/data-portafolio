"""
Framework de evaluación del asistente RAG de Frutolandia.

Corre el set de preguntas de `datos/preguntas_evaluacion.csv` contra el índice
TF-IDF y calcula métricas de calidad de retrieval y de efectividad del guardrail:

- recall@1 y recall@3: aciertos en la categoría correcta dentro del top-k.
- MRR: rank recíproco medio de la primera evidencia correcta.
- % de preguntas relevantes aceptadas y % de no relevantes rechazadas: separación
  de las dos distribuciones de score alrededor del umbral.

Exporta el detalle pregunta por pregunta (CSV) y el histograma de scores con la
línea del umbral (PNG), e imprime la tabla de métricas.

Uso:
    python evaluar.py
    python evaluar.py --umbral 0.35
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # backend sin ventana: el servidor no tiene display
import matplotlib.pyplot as plt  # noqa: E402  (debe importarse después de use)
import pandas as pd  # noqa: E402

from construir_indice import cargar_indice  # noqa: E402
from guardrails import TOP_K_POR_DEFECTO, UMBRAL_POR_DEFECTO, sanear_texto  # noqa: E402
from responder import buscar  # noqa: E402

BASE = Path(__file__).resolve().parent
RUTA_CASOS = BASE / "datos" / "preguntas_evaluacion.csv"
OUTPUTS = BASE / "outputs"
RUTA_RESULTADOS = OUTPUTS / "resultados_evaluacion.csv"
RUTA_GRAFICO = OUTPUTS / "distribucion_scores.png"

# Categoría esperada -> documento de la base de conocimiento que la contiene.
FUENTE_POR_CATEGORIA = {
    "envios": "envios-y-entregas.md",
    "productos": "productos-y-stock.md",
    "pagos": "pagos-y-facturacion.md",
    "devoluciones": "devoluciones-y-reclamos.md",
}

VERDADEROS = {"si", "sí", "true", "1"}
FALSOS = {"no", "false", "0"}


def a_booleano(valor: object) -> bool:
    """Convierte el valor de la columna `relevante` (si/no) a booleano."""
    texto = str(valor).strip().lower()
    if texto in VERDADEROS:
        return True
    if texto in FALSOS:
        return False
    raise ValueError(f"Valor no válido en la columna 'relevante': {valor!r}")


def leer_casos(ruta: Path = RUTA_CASOS) -> pd.DataFrame:
    """Lee el set de preguntas de evaluación (CSV separado por punto y coma)."""
    if not ruta.exists():
        raise FileNotFoundError(f"Falta el set de evaluación en {ruta}")
    casos = pd.read_csv(ruta, sep=";", encoding="utf-8")
    casos["relevante"] = casos["relevante"].map(a_booleano)
    return casos


def solapamiento(esperada: str, obtenida: str) -> float:
    """Proporción de palabras de la respuesta esperada que aparecen en la evidencia."""
    palabras_esperadas = set(sanear_texto(esperada).split())
    palabras_obtenidas = set(sanear_texto(obtenida).split())
    if not palabras_esperadas:
        return 0.0
    return len(palabras_esperadas & palabras_obtenidas) / len(palabras_esperadas)


def evaluar_casos(casos: pd.DataFrame, indice: dict, vectorizador, umbral: float, top_k: int) -> pd.DataFrame:
    """Recupera evidencia para cada caso y anota score, decisión y rank del acierto."""
    filas = []
    for caso in casos.itertuples(index=False):
        evidencias = buscar(caso.pregunta, indice, vectorizador, top_k)
        score = evidencias[0]["score"] if evidencias else 0.0
        fuente_esperada = FUENTE_POR_CATEGORIA.get(caso.categoria)

        rank = 0
        for posicion, evidencia in enumerate(evidencias, start=1):
            if evidencia["fuente"] == fuente_esperada:
                rank = posicion
                break

        filas.append(
            {
                "pregunta": caso.pregunta,
                "categoria": caso.categoria,
                "relevante": bool(caso.relevante),
                "score_top1": round(score, 4),
                "decision": "aceptada" if score >= umbral else "rechazada",
                "rank_categoria": rank,
                "acierto_categoria": bool(caso.relevante) and rank > 0,
                "fuente_top1": evidencias[0]["fuente"] if evidencias else "",
                "solapamiento_respuesta": (
                    round(solapamiento(caso.respuesta_esperada, evidencias[0]["respuesta"]), 3)
                    if evidencias
                    else 0.0
                ),
            }
        )
    return pd.DataFrame(filas)


def calcular_metricas(resultados: pd.DataFrame, umbral: float) -> pd.DataFrame:
    """Calcula recall@1, recall@3, MRR y la efectividad del guardrail."""
    relevantes = resultados[resultados["relevante"]]
    irrelevantes = resultados[~resultados["relevante"]]
    total_relevantes = len(relevantes)
    total_irrelevantes = len(irrelevantes)

    at1 = int(relevantes["rank_categoria"].eq(1).sum())
    at3 = int(relevantes["rank_categoria"].between(1, 3).sum())
    aceptadas = int(relevantes["decision"].eq("aceptada").sum())
    rechazadas = int(irrelevantes["decision"].eq("rechazada").sum())
    reciprocos = float((1.0 / relevantes["rank_categoria"].replace(0, float("nan"))).sum())

    def proporcion(aciertos: int, total: int) -> float:
        return float(aciertos) / total if total else 0.0

    return pd.DataFrame(
        [
            ["recall@1", proporcion(at1, total_relevantes), f"{at1}/{total_relevantes}"],
            ["recall@3", proporcion(at3, total_relevantes), f"{at3}/{total_relevantes}"],
            ["MRR", proporcion(reciprocos, total_relevantes), f"{reciprocos:.3f} acumulada"],
            ["Relevantes aceptadas", proporcion(aceptadas, total_relevantes), f"{aceptadas}/{total_relevantes}"],
            ["No relevantes rechazadas", proporcion(rechazadas, total_irrelevantes), f"{rechazadas}/{total_irrelevantes}"],
            [
                "Exactitud del guardrail",
                (aceptadas + rechazadas) / len(resultados) if len(resultados) else 0.0,
                f"{aceptadas + rechazadas}/{len(resultados)}",
            ],
        ],
        columns=["metrica", "valor", "detalle"],
    ).assign(umbral=umbral)


def graficar_distribucion(resultados: pd.DataFrame, umbral: float, ruta: Path = RUTA_GRAFICO) -> Path:
    """Genera el histograma de scores relevantes vs no relevantes con el umbral marcado."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False})

    scores_relevantes = resultados.loc[resultados["relevante"], "score_top1"]
    scores_irrelevantes = resultados.loc[~resultados["relevante"], "score_top1"]
    rangos = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(
        scores_relevantes,
        bins=rangos,
        alpha=0.75,
        color="#2b8a3e",
        label=f"Relevantes (n={len(scores_relevantes)})",
    )
    ax.hist(
        scores_irrelevantes,
        bins=rangos,
        alpha=0.75,
        color="#c92a2a",
        label=f"No relevantes (n={len(scores_irrelevantes)})",
    )
    ax.axvline(umbral, color="#343a40", linestyle="--", linewidth=1.4, label=f"Umbral = {umbral}")
    ax.set_title("Distribución de scores de similitud (coseno TF-IDF)")
    ax.set_xlabel("Similitud del mejor fragmento recuperado")
    ax.set_ylabel("Cantidad de preguntas")
    ax.legend(frameon=False)
    ax.set_xlim(0, 0.6)
    fig.tight_layout()
    fig.savefig(ruta)
    plt.close(fig)
    return ruta


def parsear_argumentos() -> argparse.Namespace:
    """Define los argumentos de la CLI del evaluador."""
    parser = argparse.ArgumentParser(description="Evalúa el retrieval y el guardrail del asistente RAG.")
    parser.add_argument(
        "--umbral",
        type=float,
        default=UMBRAL_POR_DEFECTO,
        help=f"Umbral del guardrail (default: {UMBRAL_POR_DEFECTO}).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=TOP_K_POR_DEFECTO,
        help=f"Fragmentos recuperados por consulta (default: {TOP_K_POR_DEFECTO}).",
    )
    return parser.parse_args()


def main() -> None:
    argumentos = parsear_argumentos()
    try:
        casos = leer_casos()
        indice, vectorizador = cargar_indice()
    except (FileNotFoundError, ValueError) as error:
        print(f"[error] {error}")
        return

    resultados = evaluar_casos(casos, indice, vectorizador, argumentos.umbral, argumentos.top_k)
    metricas = calcular_metricas(resultados, argumentos.umbral)

    OUTPUTS.mkdir(parents=True, exist_ok=True)
    resultados.to_csv(RUTA_RESULTADOS, sep=";", index=False, encoding="utf-8")

    print("=== Detalle por pregunta ===")
    columnas = ["pregunta", "categoria", "score_top1", "decision", "rank_categoria", "solapamiento_respuesta"]
    print(resultados[columnas].to_string(index=False))

    print(f"\n=== Métricas de evaluación (umbral {argumentos.umbral}, top-{argumentos.top_k}) ===")
    tabla = metricas.copy()
    tabla["valor"] = tabla["valor"].map(lambda valor: f"{valor:.3f}")
    print(tabla[["metrica", "valor", "detalle"]].to_string(index=False))

    grafico = graficar_distribucion(resultados, argumentos.umbral)
    print(f"\n[ok] Resultados en {RUTA_RESULTADOS.relative_to(BASE)}")
    print(f"[ok] Gráfico en {grafico.relative_to(BASE)}")


if __name__ == "__main__":
    main()
