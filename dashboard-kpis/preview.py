"""
Genera vistas previas de los KPIs del dashboard en PNG.

Permite ver los indicadores y gráficos del dashboard sin desplegar la app
Streamlit (útil para revisión rápida y para el portafolio).

Uso:
    python preview.py
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

BASE = Path(__file__).resolve().parent
OUTPUTS = BASE / "outputs"
DATA = BASE / "data" / "ventas.csv"


def cargar_datos() -> pd.DataFrame:
    df = pd.read_csv(DATA)
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df


def generar(df: pd.DataFrame) -> None:
    OUTPUTS.mkdir(exist_ok=True)
    plt.rcParams.update({"figure.dpi": 120, "axes.spines.top": False, "axes.spines.right": False})

    ventas_ciudad = df.groupby("ciudad")["venta"].sum().sort_values()
    fig, ax = plt.subplots(figsize=(7, 4))
    ventas_ciudad.plot(kind="barh", ax=ax, color="#4C78A8")
    ax.set_title(f"Ventas por ciudad — total US$ {df['venta'].sum():,.0f}")
    ax.set_xlabel("US$")
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(OUTPUTS / "ventas_por_ciudad.png")
    plt.close(fig)

    ventas_fecha = df.groupby("fecha")["venta"].sum().sort_index()
    fig, ax = plt.subplots(figsize=(7, 4))
    ventas_fecha.plot(kind="line", marker="o", ax=ax, color="#F58518")
    ax.set_title("Ventas por fecha")
    ax.set_ylabel("US$")
    fig.tight_layout()
    fig.savefig(OUTPUTS / "ventas_por_fecha.png")
    plt.close(fig)


def main() -> None:
    df = cargar_datos()
    print(f"Ventas totales: US$ {df['venta'].sum():,.0f}")
    print(f"Clientes activos: {df['cliente'].nunique()}")
    print(f"Ticket promedio: US$ {df['venta'].mean():,.0f}")
    generar(df)
    print("Vistas previas guardadas en outputs/")


if __name__ == "__main__":
    main()