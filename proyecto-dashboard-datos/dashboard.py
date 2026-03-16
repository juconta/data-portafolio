import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

# título
st.title("Dashboard de Consumo Eléctrico")

# cargar datos
data = pd.read_csv("consumo_dashboard.csv")

st.subheader("Datos del consumo")
st.write(data)

# consumo por localidad
st.subheader("Consumo promedio por localidad")
consumo_localidad = data.groupby("localidad")["consumo_kwh"].mean()
st.bar_chart(consumo_localidad)

# consumo por mes
st.subheader("Consumo por mes")
consumo_mes = data.groupby("mes")["consumo_kwh"].mean()
st.line_chart(consumo_mes)