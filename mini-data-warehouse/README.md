# Mini Data Warehouse con ETL

Construye un **mini Data Warehouse en SQLite** aplicando un pipeline ETL y un
**esquema estrella** (dimensiones + tabla de hechos) listo para consultas
analíticas en SQL.

## Problema

Los datos de ventas llegan en **tablas planas** difíciles de consultar. Un Data
Warehouse organiza la información en dimensiones y hechos, lo que habilita
consultas analíticas rápidas (ventas por ciudad, por producto, etc.).

## Arquitectura

```
CSV crudo → ETL (extraer, transformar, cargar) → SQLite (esquema estrella)
```

- `dim_cliente`, `dim_producto`, `dim_ciudad` → dimensiones
- `hecho_ventas` → tabla de hechos con montos

## Proceso

1. **Extracción** (`etl_process.py`) → `data/ventas_raw.csv`.
2. **Transformación** → normaliza a dimensiones + hechos (esquema estrella).
3. **Carga** → `datawarehouse.db` con `sqlite3`.
4. **Consulta** → ventas por ciudad y por producto vía SQL con JOIN.

## Resultados de ejemplo

| Ciudad | Total |
|---|---|
| Santiago | US$ 1.370 |
| Mendoza | US$ 1.100 |
| Buenos Aires | US$ 620 |
| Córdoba | US$ 55 |

| Producto | Total | Unidades |
|---|---|---|
| Laptop | US$ 2.300 | 2 |
| Monitor | US$ 620 | 2 |

**Insight:** las ventas se concentran en Santiago y Mendoza y en el producto
Laptop → foco de stock e inversión en esas plazas.

## Cómo reproducir

```bash
pip install -r requirements.txt
python etl_process.py
```

## Estructura

```
mini-data-warehouse/
├── etl_process.py    # extrae → transforma → carga → consulta
├── data/
│   └── ventas_raw.csv
├── datawarehouse.db  # resultado (SQLite)
└── requirements.txt
```

## Autor

Juan Pablo Contato — Licenciado en Ciencias de Datos