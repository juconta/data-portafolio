import streamlit as st
import pandas as pd

st.title("Dashboard de KPIs de Ventas")

df = pd.read_csv("ventas.csv")

ventas_totales = df["venta"].sum()
clientes = df["cliente"].nunique()

st.metric("Ventas Totales", ventas_totales)
st.metric("Clientes Activos", clientes)

st.subheader("Ventas por Ciudad")
ventas_ciudad = df.groupby("ciudad")["venta"].sum()
st.bar_chart(ventas_ciudad)

st.subheader("Ventas por Fecha")
ventas_fecha = df.groupby("fecha")["venta"].sum()
st.line_chart(ventas_fecha)

st.write("Dataset completo")
st.dataframe(df)