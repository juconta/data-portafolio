"""
Dashboard de KPIs de ventas (Streamlit).

Aplicación web para visualizar indicadores de ventas: totales, clientes activos,
ticket promedio, ventas por ciudad y evolución por fecha.

Uso:
    streamlit run dashboard_kpis.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

BASE = Path(__file__).resolve().parent
DATA = BASE / "data" / "ventas.csv"

st.set_page_config(page_title="KPIs de Ventas", page_icon="📈", layout="wide")
st.title("📈 Dashboard de KPIs de Ventas")
st.caption("Dataset sintético de ventas 2024 — 10 transacciones en 5 ciudades.")


@st.cache_data
def cargar_datos() -> pd.DataFrame:
    df = pd.read_csv(DATA)
    df["fecha"] = pd.to_datetime(df["fecha"])
    return df


df = cargar_datos()

ventas_totales = df["venta"].sum()
clientes = df["cliente"].nunique()
ticket_promedio = df["venta"].mean()

col1, col2, col3 = st.columns(3)
col1.metric("Ventas totales", f"US$ {ventas_totales:,.0f}")
col2.metric("Clientes activos", clientes)
col3.metric("Ticket promedio", f"US$ {ticket_promedio:,.0f}")

st.subheader("Ventas por ciudad")
ventas_ciudad = df.groupby("ciudad")["venta"].sum().sort_values()
st.bar_chart(ventas_ciudad)

st.subheader("Ventas por fecha")
ventas_fecha = df.set_index("fecha")["venta"].sum().sort_index()
st.line_chart(ventas_fecha)

st.subheader("Detalle de transacciones")
st.dataframe(df.sort_values("fecha", ascending=False), use_container_width=True)