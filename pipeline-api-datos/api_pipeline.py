import requests
import pandas as pd

url = "https://api.open-meteo.com/v1/forecast?latitude=-27.8&longitude=-64.3&current_weather=true"

response = requests.get(url)

data = response.json()

weather = data["current_weather"]

dataset = {
    "temperatura": weather["temperature"],
    "velocidad_viento": weather["windspeed"],
    "direccion_viento": weather["winddirection"],
    "hora": weather["time"]
}

df = pd.DataFrame([dataset])

print(df)

df.to_csv("clima_datos.csv", index=False)

print("Datos guardados en clima_datos.csv")