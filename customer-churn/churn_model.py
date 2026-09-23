"""
Modelo de predicción de churn de clientes.

Entrena una Regresión Logística y un Random Forest para predecir el abandono,
compara ambos con métricas completas y guarda el mejor modelo para producción.

Uso (después de correr generar_datos.py):
    python churn_model.py
"""

from __future__ import annotations

from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    RocCurveDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split

BASE = Path(__file__).resolve().parent
DATASET = BASE / "churn_dataset.csv"
OUTPUTS = BASE / "outputs"
MODELOS = BASE / "modelos"

FEATURES = ["edad", "meses_cliente", "uso_servicio", "pago_mensual"]
OBJETIVO = "churn"


def cargar_datos() -> pd.DataFrame:
    return pd.read_csv(DATASET)


def entrenar_modelos(X_train: pd.DataFrame, y_train: pd.Series) -> dict:
    """Entrena Regresión Logística y Random Forest y los devuelve en un dict."""
    modelos = {
        "regresion_logistica": LogisticRegression(max_iter=1000, class_weight="balanced"),
        "random_forest": RandomForestClassifier(
            n_estimators=200, random_state=42, class_weight="balanced"
        ),
    }
    return {nombre: modelo.fit(X_train, y_train) for nombre, modelo in modelos.items()}


def evaluar(modelo, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    """Evalúa un modelo y devuelve accuracy, F1 y AUC-ROC."""
    predicciones = modelo.predict(X_test)
    proba = modelo.predict_proba(X_test)[:, 1]
    return {
        "accuracy": accuracy_score(y_test, predicciones),
        "f1": f1_score(y_test, predicciones),
        "roc_auc": roc_auc_score(y_test, proba),
        "proba": proba,
        "predicciones": predicciones,
    }


def graficos(modelos: dict, resultados: dict, X_test: pd.DataFrame, y_test: pd.Series) -> None:
    """Genera curva ROC y matriz de confusión del mejor modelo en PNG."""
    OUTPUTS.mkdir(exist_ok=True)
    plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False})

    fig, ax = plt.subplots(figsize=(7, 5))
    for nombre, modelo in modelos.items():
        RocCurveDisplay.from_estimator(modelo, X_test, y_test, ax=ax, name=nombre.replace("_", " "))
    ax.set_title("Curva ROC")
    fig.tight_layout()
    fig.savefig(OUTPUTS / "curva_roc.png")
    plt.close(fig)

    mejor = max(resultados, key=lambda k: resultados[k]["f1"])
    cm = confusion_matrix(y_test, resultados[mejor]["predicciones"])
    fig, ax = plt.subplots(figsize=(6, 5))
    ax.imshow(cm, cmap="Blues")
    ax.set_xticks([0, 1], labels=["No churn", "Churn"])
    ax.set_yticks([0, 1], labels=["No churn", "Churn"])
    ax.set_xlabel("Predicción")
    ax.set_ylabel("Real")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, cm[i, j], ha="center", va="center", color="black")
    ax.set_title(f"Matriz de confusión ({mejor.replace('_', ' ')})")
    fig.tight_layout()
    fig.savefig(OUTPUTS / "matriz_confusion.png")
    plt.close(fig)


def guardar_mejor_modelo(modelos: dict, resultados: dict) -> str:
    """Guarda el modelo con mejor F1 en modelos/ para usarlo en producción."""
    mejor = max(resultados, key=lambda k: resultados[k]["f1"])
    MODELOS.mkdir(exist_ok=True)
    ruta = MODELOS / "modelo_churn.pkl"
    joblib.dump(modelos[mejor], ruta)
    return mejor, ruta


def main() -> None:
    df = cargar_datos()
    X, y = df[FEATURES], df[OBJETIVO]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    modelos = entrenar_modelos(X_train, y_train)
    resultados = {nombre: evaluar(modelo, X_test, y_test) for nombre, modelo in modelos.items()}

    print("=== Comparación de modelos ===")
    for nombre, r in resultados.items():
        print(
            f"{nombre:<22} accuracy={r['accuracy']:.3f}  "
            f"F1={r['f1']:.3f}  AUC-ROC={r['roc_auc']:.3f}"
        )

    mejor, ruta = guardar_mejor_modelo(modelos, resultados)
    print(f"\nMejor modelo: {mejor} (guardado en {ruta.relative_to(BASE)})")

    print("\n=== Reporte de clasificación (mejor modelo) ===")
    print(
        classification_report(y_test, resultados[mejor]["predicciones"], target_names=["No churn", "Churn"])
    )

    graficos(modelos, resultados, X_test, y_test)
    print(f"\nGráficos guardados en outputs/")


if __name__ == "__main__":
    main()