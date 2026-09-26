# Clasificación de Mensajes de Atención al Cliente (NLP)

Clasifica automáticamente los **mensajes de los clientes** en 4 categorías
(facturación, problema técnico, consulta, reclamo) usando **Naive Bayes** sobre
texto en español, para derivar cada mensaje al área correcta de soporte.

## Problema

Un centro de atención recibe cientos de mensajes por día. **Clasificarlos
manualmente consume horas** de agentes. Este modelo los etiqueta
automáticamente para enrutarlos sin intervención humana.

## Datos

- Dataset sintético reproducible: 180 mensajes en español, 4 categorías (45 cada una).
- Se genera con `generar_datos.py` (semilla fija).

## Proceso

1. **Datos** (`generar_datos.py`) → genera `mensajes_clientes.csv`.
2. **Entrenamiento** (`nlp_clientes.py`):
   - `CountVectorizer` convierte textos en vectores de tokens.
   - `Multinomial Naive Bayes` clasifica las categorías.
   - Split estratificado 75/25.
3. **Producción** → modelo y vectorizador guardados en `modelos/` (joblib)
   para reutilizarlos en una API o bot.

## Resultados (reporte por categoría)

El modelo alcanza **91% de exactitud ponderada** sobre el set de prueba,
con F1 >0.90 en las 4 categorías. Ejemplos de clasificación real:

```
Mensaje: "Mi factura llegó duplicada"          → facturacion
Mensaje: "No tengo señal de internet"          → problema_tecnico
```

## Cómo reproducir

```bash
pip install -r requirements.txt
python generar_datos.py
python nlp_clientes.py
```

## Estructura

```
nlp-atencion-clientes/
├── mensajes_clientes.csv        # dataset (generado)
├── generar_datos.py             # genera el dataset sintético
├── nlp_clientes.py              # entrenamiento + evaluación + export
├── modelos/                     # clasificador + vectorizador (joblib)
└── requirements.txt
```

## Autor

Juan Pablo Contato — Licenciado en Ciencias de Datos