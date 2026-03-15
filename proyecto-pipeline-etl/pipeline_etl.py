import pandas as pd

# EXTRACT
print("Extrayendo datos...")
data = pd.read_csv("datos_clientes.csv")

print("\nDatos originales:")
print(data)

# TRANSFORM
print("\nTransformando datos...")

# eliminar filas con datos faltantes
data_clean = data.dropna()

# crear nueva columna de consumo anual estimado
data_clean["consumo_anual"] = data_clean["consumo_kwh"] * 12

print("\nDatos transformados:")
print(data_clean)

# LOAD
print("\nGuardando datos procesados...")
data_clean.to_csv("datos_procesados.csv", index=False)

print("\nPipeline ETL finalizado correctamente.")