"""
Clasificador de mensajes de atención al cliente (NLP).

Clasifica automáticamente los mensajes de los clientes en 4 categorías
(facturación, problema técnico, consulta, reclamo) para derivarlos al área
correcta sin intervención manual.

Uso (después de correr generar_datos.py):
    python nlp_clientes.py
"""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB

BASE = Path(__file__).resolve().parent
DATASET = BASE / "mensajes_clientes.csv"
MODELOS = BASE / "modelos"


def cargar_datos() -> pd.DataFrame:
    return pd.read_csv(DATASET)


def entrenar(df: pd.DataFrame) -> tuple[object, object, object]:
    """Vectoriza los mensajes y entrena un clasificador Naive Bayes."""
    vectorizer = CountVectorizer()
    X = vectorizer.fit_transform(df["mensaje"])
    y = df["categoria"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=42, stratify=y
    )

    model = MultinomialNB()
    model.fit(X_train, y_train)
    return model, vectorizer, (X_test, y_test)


def evaluar(model, X_test, y_test) -> None:
    """Imprime el reporte de clasificación por categoría."""
    predicciones = model.predict(X_test)
    print("=== Reporte de clasificación por categoría ===")
    print(classification_report(y_test, predicciones, zero_division=0))


def guardar_modelo(model, vectorizer) -> None:
    """Guarda modelo y vectorizador para usarlos en producción."""
    MODELOS.mkdir(exist_ok=True)
    joblib.dump(model, MODELOS / "clasificador_mensajes.pkl")
    joblib.dump(vectorizer, MODELOS / "vectorizador.pkl")
    print(f"Modelo guardado en {MODELOS.relative_to(BASE)}/")


def clasificar(model, vectorizer, mensaje: str) -> str:
    """Clasifica un mensaje nuevo usando el modelo entrenado."""
    vector = vectorizer.transform([mensaje])
    return model.predict(vector)[0]


def main() -> None:
    df = cargar_datos()
    model, vectorizer, (X_test, y_test) = entrenar(df)
    evaluar(model, X_test, y_test)
    guardar_modelo(model, vectorizer)

    for ejemplo in ["Mi factura llegó duplicada", "No tengo señal de internet"]:
        print(f"\nMensaje: '{ejemplo}' -> categoría: {clasificar(model, vectorizer, ejemplo)}")


if __name__ == "__main__":
    main()