"""
Generador del dataset de churn (dataset sintético reproducible).

Crea `churn_dataset.csv` con 500 clientes y una probabilidad de abandono
que depende de la antigüedad del cliente, el uso del servicio y el precio.

Uso:
    python generar_datos.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
OUT = BASE / "churn_dataset.csv"
N_CLIENTES = 500


def generar() -> pd.DataFrame:
    rng = np.random.default_rng(42)

    edad = rng.integers(18, 71, N_CLIENTES)
    meses_cliente = rng.integers(1, 37, N_CLIENTES)
    uso_servicio = rng.integers(20, 101, N_CLIENTES)
    pago_mensual = rng.integers(15, 61, N_CLIENTES)

    # a menor antigüedad y uso, y mayor precio → más churn (con ruido)
    score = (
        -0.12 * meses_cliente
        + 0.10 * (pago_mensual - 37)
        + 0.06 * (50 - uso_servicio)
        + 0.55
        + rng.normal(0, 0.45, N_CLIENTES)
    )
    prob = 1 / (1 + np.exp(-score))
    churn = (rng.random(N_CLIENTES) < prob).astype(int)

    return pd.DataFrame(
        {
            "cliente_id": np.arange(1, N_CLIENTES + 1),
            "edad": edad,
            "meses_cliente": meses_cliente,
            "uso_servicio": uso_servicio,
            "pago_mensual": pago_mensual,
            "churn": churn,
        }
    )


def main() -> None:
    df = generar()
    df.to_csv(OUT, index=False)
    print(f"Dataset generado: {OUT.name} ({len(df)} registros)")
    print(f"Clientes con churn: {df['churn'].sum()} ({df['churn'].mean():.1%})")


if __name__ == "__main__":
    main()