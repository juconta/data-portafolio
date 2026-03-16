import requests
from bs4 import BeautifulSoup
import pandas as pd

url = "https://books.toscrape.com/"

response = requests.get(url)
soup = BeautifulSoup(response.text, "html.parser")

libros = []

for book in soup.find_all("article", class_="product_pod"):
    titulo = book.h3.a["title"]
    precio = book.find("p", class_="price_color").text
    
    libros.append({
        "titulo": titulo,
        "precio": precio
    })

df = pd.DataFrame(libros)

print(df)

df.to_csv("productos.csv", index=False)

print("Datos guardados en productos.csv")
