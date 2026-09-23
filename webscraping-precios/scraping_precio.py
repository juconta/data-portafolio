"""
Scraping de productos desde Books to Scrape.

Extrae títulos y precios de la tienda de prueba Books to Scrape
(sitio público diseñado para practicar scraping), limpia los precios
y guarda el resultado en `data/productos.csv`.

Uso:
    python scraping_precio.py
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parent
OUT = BASE / "data" / "productos.csv"
URL = "https://books.toscrape.com/"
TIMEOUT = 15


def extraer_libros() -> list[dict]:
    """Descarga la página y extrae título y precio de cada libro."""
    response = requests.get(URL, timeout=TIMEOUT)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    libros = []
    for libro in soup.find_all("article", class_="product_pod"):
        titulo = libro.h3.a["title"]
        precio_texto = libro.find("p", class_="price_color").text
        libros.append({"titulo": titulo, "precio": limpiar_precio(precio_texto)})
    return libros


def limpiar_precio(precio_texto: str) -> float:
    """Convierte '£51.77' (o variantes) en el número flotante 51.77."""
    coincidencia = re.search(r"\d+[.,]\d{2}", precio_texto)
    if not coincidencia:
        return 0.0
    return float(coincidencia.group().replace(",", "."))


def guardar(libros: list[dict]) -> None:
    OUT.parent.mkdir(exist_ok=True)
    df = pd.DataFrame(libros)
    df = df.sort_values("precio", ascending=False).reset_index(drop=True)
    df.to_csv(OUT, index=False)
    print(f"{len(df)} libros guardados en {OUT.relative_to(BASE)}")
    print(f"Precio promedio: {df['precio'].mean():.2f} GBP")
    print(f"Libro más caro: {df.iloc[0]['titulo']} ({df.iloc[0]['precio']:.2f} GBP)")


def main() -> None:
    libros = extraer_libros()
    guardar(libros)


if __name__ == "__main__":
    main()