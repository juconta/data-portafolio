import pandas as pd
import sqlite3

# cargar datos crudos
df = pd.read_csv("ventas_raw.csv")

print("Datos originales")
print(df.head())

# transformación
ventas_ciudad = df.groupby("ciudad")["venta"].sum().reset_index()

print("\nVentas por ciudad")
print(ventas_ciudad)

# crear conexión a base de datos
conn = sqlite3.connect("datawarehouse.db")

# cargar datos al warehouse
df.to_sql("ventas", conn, if_exists="replace", index=False)
ventas_ciudad.to_sql("ventas_ciudad", conn, if_exists="replace", index=False)

print("\nDatos cargados en Data Warehouse")

conn.close()