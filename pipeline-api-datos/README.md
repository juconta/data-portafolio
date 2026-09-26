# Pipeline de Datos desde API (Clima LatAm)

Pipeline que **extrae el clima actual de 7 ciudades latinoamericanas** desde la
API pública **Open-Meteo**, las estandariza en un esquema común y las guarda en
un dataset CSV listo para análisis o consumo downstream.

## Problema

Para alimentar un análisis o un modelo se necesita **obtener datos de forma
automática y reproducible** desde una fuente externa. Este proyecto muestra el
patrón extraer → estandarizar → guardar con una API pública real.

## Datos

- Fuente: [Open-Meteo](https://open-meteo.com/) — API pública y gratuita (sin API key).
- 7 ciudades: Buenos Aires, Santiago, Bogotá, Ciudad de México, Lima, Quito y Montevideo.
- Variables: temperatura, velocidad y dirección del viento, día/noche, fecha.

## Proceso

1. **Extracción** (`api_pipeline.py`) → consulta la API por ciudad con `requests`.
2. **Estandarización** → mapea la respuesta JSON a un esquema fijo en español.
3. **Carga** → `data/clima_datos.csv` (una fila por ciudad y snapshot).

## Cómo reproducir

```bash
pip install -r requirements.txt
python api_pipeline.py
```

## Estructura

```
pipeline-api-datos/
├── api_pipeline.py   # extrae → estandariza → guarda
├── data/
│   └── clima_datos.csv   # snapshot del clima en LatAm
└── requirements.txt
```

## Autor

Juan Pablo Contato — Licenciado en Ciencias de Datos