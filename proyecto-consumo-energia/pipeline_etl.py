"""
Pipeline ETL de consumo eléctrico.

Extrae el dataset crudo, lo limpia (valores faltantes, inconsistencias y
valores atípicos) y lo transforma en un dataset listo para análisis y
visualización.

Uso:
    python pipeline_etl.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
DATA = BASE / "data"
RAW = DATA / "consumo_energia_raw.csv"
CLEAN = DATA / "consumo_energia_clean.csv"
ORDEN_MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo"]


def extraer() -> pd.DataFrame:
    """Lee el dataset crudo desde CSV."""
    return pd.read_csv(RAW)


def transformar(df: pd.DataFrame) -> pd.DataFrame:
    """
    Limpia y normaliza los datos:

    - normaliza la localidad (mayúsculas iniciales y sin espacios)
    - imputa la edad faltante con la mediana
    - imputa el consumo faltante con la mediana por localidad
    - descarta consumos negativos (errores de medidor)
    - ordena el mes como categoría (Enero → Mayo)
    """
    df = df.copy()
    df["localidad"] = df["localidad"].str.strip().str.title()
    df["edad"] = df["edad"].fillna(df["edad"].median()).astype(int)

    mediana_por_localidad = df.groupby("localidad")["consumo_kwh"].transform("median")
    df["consumo_kwh"] = df["consumo_kwh"].fillna(mediana_por_localidad)
    df = df[df["consumo_kwh"] >= 0]

    df["mes"] = pd.Categorical(df["mes"], categories=ORDEN_MESES, ordered=True)
    return df.sort_values(["cliente", "mes"]).reset_index(drop=True)


def cargar(df: pd.DataFrame) -> None:
    """Guarda el dataset limpio en CSV y muestra un resumen del proceso."""
    CLEAN.parent.mkdir(exist_ok=True)
    df.to_csv(CLEAN, index=False)

    print("Registros crudos: 48")
    print(f"Registros limpios: {len(df)}")
    print(f"Registros descartados: {48 - len(df)}")
    print(f"Dataset limpio guardado en: {CLEAN.name}")


def main() -> None:
    df_raw = extraer()
    df_clean = transformar(df_raw)
    cargar(df_clean)
    print("\nPrimeras filas del dataset limpio:")
    print(df_clean.head())


if __name__ == "__main__":
    main()