import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("customers.csv")

print("Primeras filas del dataset")
print(df.head())

print("\nEstadísticas generales")
print(df.describe())

print("\nCompras promedio por ciudad")
print(df.groupby("ciudad")["compras"].mean())

# gráfico compras por cliente
plt.bar(df["cliente_id"], df["compras"])
plt.xlabel("Cliente")
plt.ylabel("Número de compras")
plt.title("Compras por cliente")

plt.show()