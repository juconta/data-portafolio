import pandas as pd
import matplotlib.pyplot as plt

# Cargar dataset
data = pd.read_csv("consumo_energia.csv")

# Mostrar primeras filas
print("Primeros datos del dataset:")
print(data.head())

# Consumo promedio
promedio = data["consumo_kwh"].mean()
print("Consumo promedio:", promedio)

# Consumo por localidad
consumo_localidad = data.groupby("localidad")["consumo_kwh"].mean()
print("\nConsumo promedio por localidad:")
print(consumo_localidad)

# Gráfico de consumo por localidad
consumo_localidad.plot(kind="bar")
plt.title("Consumo promedio por localidad")
plt.ylabel("kWh")
plt.show()