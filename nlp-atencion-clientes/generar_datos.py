"""
Generador del dataset de mensajes de clientes (dataset sintético reproducible).

Crea `mensajes_clientes.csv` combinando plantillas en español de 4 categorías:
facturación, problema técnico, consulta y reclamo.

Uso:
    python generar_datos.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path(__file__).resolve().parent
OUT = BASE / "mensajes_clientes.csv"
POR_CATEGORIA = 45
SEED = 7

PLANTILLAS = {
    "facturacion": [
        "No puedo pagar mi factura",
        "La factura llegó muy alta este mes",
        "No entiendo mi factura",
        "Me llegó un cargo que no reconozco",
        "Quiero descargar mi factura del mes pasado",
        "Necesito que me recalcularan el monto",
        "Por qué me cobraron dos veces",
        "El débito automático no me funcionó",
    ],
    "problema_tecnico": [
        "Mi internet no funciona",
        "El servicio se corta constantemente",
        "La conexión es muy lenta",
        "No tengo señal de wifi en casa",
        "Mi módem parpadea en rojo",
        "Se cae la señal cuando llueve",
        "La velocidad que tengo no es la contratada",
        "Necesito que reinicien mi servicio",
    ],
    "consulta": [
        "Necesito información del servicio",
        "Quiero saber los planes disponibles",
        "Necesito hablar con soporte",
        "Qué cobertura tienen en mi zona",
        "Quiero cambiar mi plan actual",
        "Dónde veo mi consumo al día",
        "Me interesa contratar internet",
        "Cómo hago para mudar mi servicio",
    ],
    "reclamo": [
        "No me devuelven el dinero que pagué",
        "Quiero realizar un reclamo formal",
        "Estoy disconforme con la atención",
        "Hace semanas que espero una solución",
        "Me cortaron el servicio injustamente",
        "Quiero elevar una queja",
        "El técnico nunca llegó a mi casa",
        "Exijo una respuesta por escrito",
    ],
}


def generar() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    sufijos = ["", " por favor", " urgente", " gracias", " hoy"]
    categorias = list(PLANTILLAS)
    filas = []
    for categoria in categorias:
        for i in range(POR_CATEGORIA):
            plantillas = PLANTILLAS[categoria]
            plantilla = plantillas[i % len(plantillas)]
            mensaje = plantilla + rng.choice(sufijos)

            # ruido realista: 8% de los mensajes incluye vocabulario de otra
            # categoría, lo que produce errores de clasificación como en producción
            if rng.random() < 0.08:
                otra = rng.choice([c for c in categorias if c != categoria])
                mensaje += " " + rng.choice(PLANTILLAS[otra])

            filas.append({"mensaje": mensaje, "categoria": categoria})
    df = pd.DataFrame(filas)
    return df.sample(frac=1, random_state=SEED).reset_index(drop=True)


def main() -> None:
    df = generar()
    df.to_csv(OUT, index=False)
    print(f"Dataset generado: {OUT.name} ({len(df)} mensajes)")
    print(df["categoria"].value_counts().to_string())


if __name__ == "__main__":
    main()