# Juan Pablo Contato — Portafolio de Datos

Hola! Soy **Licenciado en Ciencias de Datos** y Técnico Superior en Desarrollo
de Sistemas de Software. Actualmente curso una Diplomatura en Ingeniería de
Datos (ICARO, UNC).

Este repositorio es mi **portafolio de proyectos de Ciencia e Ingeniería de
Datos**: cada proyecto resuelve un problema de negocio real con datos, incluye
los resultados cuantificables y se puede reproducir de punta a punta.

![Python](https://img.shields.io/badge/Python-3.9+-FFD43B?style=flat-square&logo=python&logoColor=black)
![Pandas](https://img.shields.io/badge/Pandas-2.0+-150458?style=flat-square&logo=pandas)
![Scikit-learn](https://img.shields.io/badge/Scikit--learn-1.3+-F7931E?style=flat-square&logo=scikit-learn&logoColor=black)
![SQL](https://img.shields.io/badge/SQL-SQLite-003B57?style=flat-square&logo=sqlite)
![Streamlit](https://img.shields.io/badge/Streamlit-1.30+-FF4B4B?style=flat-square&logo=streamlit)
![Matplotlib](https://img.shields.io/badge/Matplotlib-3.8+-11557C?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)

## Áreas de trabajo

- **Ciencia de Datos**: modelos de clasificación, NLP y análisis explotatorio.
- **Ingeniería de Datos**: pipelines ETL, APIs, data warehouses y dashboards.
- **Visualización**: dashboards interactivos con Streamlit.
- **IA aplicada**: asistentes con recuperación de documentos (RAG), guardrails y evaluación.
- **Aplicaciones**: automatización con agentes de IA, web con IA y seguridad básica.

## Proyectos

| Proyecto | Rol / Stack | Resultado destacado |
|---|---|---|
| [Customer Churn Prediction](customer-churn/) | ML · Scikit-learn | Random Forest, **F1 0.76 / AUC-ROC 0.94** |
| [Clasificación de Mensajes (NLP)](nlp-atencion-clientes/) | NLP · Naive Bayes | 4 categorías, **91% exactitud** |
| [Dashboard de KPIs de Ventas](dashboard-kpis/) | Dashboard · Streamlit | KPIs interactivos de ventas |
| [Pipeline de Datos desde API](pipeline-api-datos/) | Ingeniería · requests | Clima de **7 ciudades LatAm** |
| [Mini Data Warehouse](mini-data-warehouse/) | Ingeniería · SQLite | Esquema estrella + consultas SQL |
| [Web Scraping de Precios](webscraping-precios/) | Scraping · BeautifulSoup | 20 libros y precios limpios |
| [Consumo de Energía (E2E)](proyecto-consumo-energia/) | ETL → Análisis → Dashboard | Pipeline completo de consumo eléctrico |
| [Asistente RAG Confiable](rag-asistente-confiable/) | RAG · Evaluación | **100% recall@1** en 16 preguntas + guardrail |
| [Automatización con Agentes de IA](agentes-ia-automatizacion/) | Agentes · Orquestación | Reintentos, fallback y monitoreo reproducibles |
| [Web con Asistente de IA](web-integracion-ia/) | FastAPI · IA | Web con chat sobre FAQs, sin dependencias de LLM |
| [Auditoría de Seguridad](seguridad-auditoria-basica/) | Seguridad · Análisis estático | 29 hallazgos detectados → **0 tras la corrección** |

## Contenido de cada proyecto

Cada proyecto incluye: **problema → datos → proceso → resultados → cómo
reproducir**, con scripts ejecutables, código refactorizado con `main()` y
rutas portables, y salidas (gráficos, modelos o bases de datos) commiteadas
para ver resultados sin correr nada.

## Cómo reproducir

Requisito: **Python 3.9+**.

```bash
# Dependencias e instalación
pip install "pandas>=2.0"      # (o `pip install -r requirements.txt` por proyecto)
```

Ejecución por proyecto según su README. Por ejemplo:

```bash
cd customer-churn
python generar_datos.py   # dataset sintético
python churn_model.py     # entrena + evalúa + exporta modelo
```

## Contacto

- **GitHub**: [github.com/juconta](https://github.com/juconta)
- **Correo**: juancontato@gmail.com
- **LinkedIn**: *completá tu URL aquí (ej: linkedin.com/in/tu-usuario)*

¿Buscás sumarte a tu equipo? Escribime, respondo el mismo día.