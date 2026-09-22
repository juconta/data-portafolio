# Proyecto: Análisis de Consumo de Energía

Análisis end-to-end del consumo eléctrico de clientes: **ETL → Análisis → Dashboard interactivo**.
Es un caso completo que muestra el ciclo de vida de los datos en un mismo proyecto.

## Problema

Una empresa de energía necesita entender **cómo y dónde consumen sus clientes** para
detectar patrones por localidad y por mes, y tener una única vista (dashboard) para
tomar decisiones.

## Datos

- Fuente: dataset sintético de ejemplo (48 registros, 10 clientes, 3 localidades).
- Archivo crudo: `data/consumo_energia_raw.csv` — incluye problemas reales a limpiar:
  edades faltantes, consumos faltantes, valores negativos y nombres de localidad inconsistentes.

## Proceso

1. **ETL** (`pipeline_etl.py`) → limpia el dataset crudo y genera `data/consumo_energia_clean.csv`
   - imputa edades y consumos faltantes
   - descarta valores negativos (errores de medidor)
   - normaliza los nombres de localidad
2. **Análisis** (`analisis_consumo.py`) → calcula KPIs e imprime los resultados:
   - consumo total del período: **20.160 kWh**
   - consumo promedio por cliente: **2.016 kWh**
   - genera gráficos en `outputs/`
3. **Dashboard** (`dashboard.py`) → vista interactiva con Streamlit:
   - KPIs (consumo total, clientes activos, consumo máximo)
   - consumo por localidad (bar chart) y por mes (line chart)
   - tabla pivote de consumo por cliente

## Resultados clave

| Localidad | Consumo promedio por cliente (kWh) |
|---|---|
| Capital | ~512 |
| Termas | ~455 |
| Banda | ~290 |

Los clientes de la localidad **Capital** consumen casi el doble que los de **Banda**:
un dato accionable para campañas de eficiencia energética focalizadas.

## Cómo reproducir

```bash
pip install -r requirements.txt
python pipeline_etl.py
python analisis_consumo.py
streamlit run dashboard.py
```

## Estructura

```
proyecto-consumo-energia/
├── data/
│   ├── consumo_energia_raw.csv      # entrada (con errores a limpiar)
│   └── consumo_energia_clean.csv    # salida del ETL
├── outputs/                         # gráficos PNG del análisis
├── pipeline_etl.py                  # extrae → transforma → carga
├── analisis_consumo.py              # KPIs + gráficos
├── dashboard.py                     # app Streamlit
└── requirements.txt
```

## Autor

Juan Pablo Contato — Licenciado en Ciencias de Datos