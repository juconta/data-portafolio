# Web Scraping de Precios de Productos

Extrae **títulos y precios de libros** desde **Books to Scrape** (sitio público
de prueba), limpia los datos y los deja listos para análisis de precios.

## Problema

Una tarea común en datos es **recolectar información de la web** para
comparar precios o armar catálogos. Este proyecto hace scraping real desde
una tienda pública de práctica y estructura los datos en CSV.

## Datos

- Fuente: [books.toscrape.com](https://books.toscrape.com/) — 20 libros por página.
- Precios en libras esterlinas (GBP), con limpieza de formato (`£51.77` → `51.77`).
- Resultado: `data/productos.csv` (título + precio, ordenado por precio).

## Proceso

1. **Extracción** (`scraping_precio.py`) → `requests` + `BeautifulSoup`
   extraen los artículos `product_pod` de la página.
2. **Limpieza** → el precio se normaliza con regex de string a número.
3. **Carga** → `data/productos.csv` ordenado de mayor a menor precio.

## Resultados

- 20 libros extraídos de la página principal.
- Precio promedio: **£38.05 GBP** · libro más caro: **£57.25 GBP** (corrida de referencia).

> El sitio es de práctica pública (permite scraping); se respeta su uso para
> fines educativos. Para sitios reales hay que validar los términos de uso.

## Cómo reproducir

```bash
pip install -r requirements.txt
python scraping_precio.py
```

## Estructura

```
webscraping-precios/
├── scraping_precio.py   # extracción + limpieza + carga
├── data/
│   └── productos.csv    # resultado (título + precio)
└── requirements.txt
```

## Autor

Juan Pablo Contato — Licenciado en Ciencias de Datos