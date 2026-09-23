"""
Dashboard interactivo de consumo eléctrico (Streamlit).

Muestra KPIs y gráficos del dataset limpio generado por pipeline_etl.py.

Uso (después de correr pipeline_etl.py):
    streamlit run dashboard.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

BASE = Path(__file__).resolve().parent
CLEAN = BASE / "data" / "consumo_energia_clean.csv"

st.set_page_config(page_title="Consumo Eléctrico", page_icon="⚡", layout="wide")

st.title("⚡ Dashboard de Consumo Eléctrico")
st.caption("Dataset limpio generado por el pipeline ETL del mismo proyecto.")


@st.cache_data
def cargar_datos() -> pd.DataFrame:
    return pd.read_csv(CLEAN)


df = cargar_datos()

total = df["consumo_kwh"].sum()
clientes = df["cliente"].nunique()
promedio_localidad = df.groupby("localidad")["consumo_kwh"].mean().round(1)

col1, col2, col3 = st.columns(3)
col1.metric("Consumo total", f"{total:,.0f} kWh")
col2.metric("Clientes activos", clientes)
col3.metric("Consumo máximo mensual", f"{df['consumo_kwh'].max():,.0f} kWh")

st.subheader("Consumo promedio por localidad")
st.bar_chart(promedio_localidad)

st.subheader("Consumo total por mes")
consumo_mes = df.groupby("mes", observed=True)["consumo_kwh"].sum()
st.line_chart(consumo_mes)

st.subheader("Detalle por cliente")
st.dataframe(
    df.pivot_table(
        index="cliente",
        columns="mes",
        values="consumo_kwh",
        aggfunc="sum",
        fill_value=0,
        observed=True,
    )
)