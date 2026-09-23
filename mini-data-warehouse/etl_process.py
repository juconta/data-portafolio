"""
Mini Data Warehouse con ETL (esquema estrella).

Extrae ventas desde CSV, las transforma en dimensiones y hechos, y las carga
en una base SQLite lista para consultas analíticas.

Uso:
    python etl_process.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parent
RAW = BASE / "data" / "ventas_raw.csv"
DB = BASE / "datawarehouse.db"


def extraer() -> pd.DataFrame:
    return pd.read_csv(RAW)


def transformar(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Convierte la tabla plana en dimensiones + tabla de hechos (esquema estrella)."""
    dim_cliente = df[["cliente"]].drop_duplicates().reset_index(drop=True)
    dim_cliente["cliente_id"] = dim_cliente.index + 1

    dim_producto = df[["producto"]].drop_duplicates().reset_index(drop=True)
    dim_producto["producto_id"] = dim_producto.index + 1

    dim_ciudad = df[["ciudad"]].drop_duplicates().reset_index(drop=True)
    dim_ciudad["ciudad_id"] = dim_ciudad.index + 1

    hechos = df.merge(dim_cliente, on="cliente") \
        .merge(dim_producto, on="producto") \
        .merge(dim_ciudad, on="ciudad")
    hechos = hechos[["id", "cliente_id", "producto_id", "ciudad_id", "venta"]]
    hechos = hechos.rename(columns={"id": "venta_id"})

    return dim_cliente, dim_producto, dim_ciudad, hechos


def cargar(dim_cliente, dim_producto, dim_ciudad, hechos) -> None:
    """Carga dimensiones y hechos en SQLite (esquema estrella)."""
    conn = sqlite3.connect(DB)
    with conn:
        dim_cliente.to_sql("dim_cliente", conn, if_exists="replace", index=False)
        dim_producto.to_sql("dim_producto", conn, if_exists="replace", index=False)
        dim_ciudad.to_sql("dim_ciudad", conn, if_exists="replace", index=False)
        hechos.to_sql("hecho_ventas", conn, if_exists="replace", index=False)
    conn.close()
    print(f"Data Warehouse generado: {DB.name}")


def consultar() -> None:
    """Ejecuta las consultas analíticas del warehouse."""
    conn = sqlite3.connect(DB)
    consultas = {
        "Ventas por ciudad": """
            SELECT c.ciudad, SUM(h.venta) AS total
            FROM hecho_ventas h
            JOIN dim_ciudad c ON c.ciudad_id = h.ciudad_id
            GROUP BY c.ciudad ORDER BY total DESC
        """,
        "Ventas por producto": """
            SELECT p.producto, SUM(h.venta) AS total, COUNT(*) AS unidades
            FROM hecho_ventas h
            JOIN dim_producto p ON p.producto_id = h.producto_id
            GROUP BY p.producto ORDER BY total DESC
        """,
    }
    for nombre, sql in consultas.items():
        print(f"\n=== {nombre} ===")
        print(pd.read_sql_query(sql, conn).to_string(index=False))
    conn.close()


def main() -> None:
    df = extraer()
    tablas = transformar(df)
    cargar(*tablas)
    consultar()


if __name__ == "__main__":
    main()