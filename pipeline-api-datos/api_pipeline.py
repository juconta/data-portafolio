"""
Pipeline de datos desde API (Open-Meteo).

Extrae el clima actual de varias ciudades latinoamericanas desde la API pública
Open-Meteo, lo estandariza y lo guarda en un dataset CSV para análisis.

Uso:
    python api_pipeline.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

BASE = Path(__file__).resolve().parent
OUT = BASE / "data" / "clima_datos.csv"
URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 15

CIUDADES = {
    "Buenos Aires": (-34.60, -58.38),
    "Santiago": (-33.45, -70.67),
    "Bogotá": (4.71, -74.07),
    "Ciudad de México": (19.43, -99.13),
    "Lima": (-12.05, -77.04),
    "Quito": (-0.18, -78.47),
    "Montevideo": (-34.90, -56.16),
}


def extraer_clima(ciudad: str, lat: float, lon: float) -> dict:
    """Obtiene el clima actual de una ciudad desde Open-Meteo."""
    params = {"latitude": lat, "longitude": lon, "current_weather": "true", "timezone": "auto"}
    response = requests.get(URL, params=params, timeout=TIMEOUT)
    response.raise_for_status()

    clima = response.json()["current_weather"]
    return {
        "ciudad": ciudad,
        "fecha": clima["time"],
        "temperatura_c": clima["temperature"],
        "velocidad_viento_kmh": clima["windspeed"],
        "direccion_viento": clima["winddirection"],
        "is_day": clima["is_day"],
    }


def main() -> None:
    registros = [extraer_clima(ciudad, lat, lon) for ciudad, (lat, lon) in CIUDADES.items()]
    df = pd.DataFrame(registros)

    OUT.parent.mkdir(exist_ok=True)
    df.to_csv(OUT, index=False)

    print("=== Clima actual en LatAm ===")
    print(df.to_string(index=False))
    print(f"\nDataset guardado en {OUT.relative_to(BASE)} ({len(df)} ciudades)")


if __name__ == "__main__":
    main()