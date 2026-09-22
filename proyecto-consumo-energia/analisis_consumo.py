"""
Análisis exploratorio de consumo eléctrico.

Calcula KPIs de consumo, los imprime en consola y genera gráficos PNG
en la carpeta `outputs/` para ver los resultados sin ejecutar el código.

Uso (después de correr pipeline_etl.py):
    python analisis_consumo.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

BASE = Path(__file__).resolve().parent
OUTPUTS = BASE / "outputs"
CLEAN = BASE / "data" / "consumo_energia_clean.csv"


def cargar_datos() -> pd.DataFrame:
    return pd.read_csv(CLEAN)


def calcular_kpis(df: pd.DataFrame) -> None:
    """Imprime los KPIs principales del dataset."""
    clientes = df["cliente"].nunique()
    total = df["consumo_kwh"].sum()
    promedio_mensual = df.groupby("cliente")["consumo_kwh"].sum().mean()

    print("=== KPIs de consumo eléctrico ===")
    print(f"Clientes activos: {clientes}")
    print(f"Consumo total del período: {total:,.0f} kWh")
    print(f"Consumo promedio por cliente: {promedio_mensual:,.1f} kWh")
    print("\n=== Consumo promedio por localidad ===")
    print(df.groupby("localidad")["consumo_kwh"].mean().round(1))
    print("\n=== Consumo promedio por mes ===")
    print(df.groupby("mes", observed=True)["consumo_kwh"].mean().round(1))


def graficar(df: pd.DataFrame) -> None:
    """Genera los gráficos del análisis en PNG."""
    OUTPUTS.mkdir(exist_ok=True)
    plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False})

    consumo_localidad = df.groupby("localidad")["consumo_kwh"].mean().sort_values()
    fig, ax = plt.subplots(figsize=(8, 5))
    consumo_localidad.plot(kind="barh", ax=ax, color="#4C78A8")
    ax.set_title("Consumo promedio por localidad (kWh)")
    ax.set_xlabel("kWh")
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(OUTPUTS / "consumo_por_localidad.png")
    plt.close(fig)

    consumo_mes = df.groupby("mes", observed=True)["consumo_kwh"].sum()
    fig, ax = plt.subplots(figsize=(8, 5))
    consumo_mes.plot(kind="line", marker="o", ax=ax, color="#F58518")
    ax.set_title("Consumo total por mes (kWh)")
    ax.set_xlabel("Mes")
    ax.set_ylabel("kWh")
    fig.tight_layout()
    fig.savefig(OUTPUTS / "consumo_por_mes.png")
    plt.close(fig)


def main() -> None:
    df = cargar_datos()
    calcular_kpis(df)
    graficar(df)
    print("\nGráficos guardados en outputs/")


if __name__ == "__main__":
    main()