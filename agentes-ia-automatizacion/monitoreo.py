"""Monitoreo de la ejecución: registro de eventos en JSONL y consolidación del log.

Cada evento (inicio de corrida, paso, intento, espera de backoff, fallback,
alerta, fin) se anexa a ``outputs/log_ejecucion.jsonl`` como una línea JSON
autocontenida. El archivo es *append-only*: el historial de corridas se puede
reprocesar después (métricas, alerting, post-mortem) sin volver a ejecutar el
proceso.

A diferencia de los agentes simulados, esta parte es directamente productive:
en producción el mismo esquema de eventos se envía a un collector de logs
(OpenTelemetry, CloudWatch, Loki) o a una base de datos de series.

Uso:
    import monitoreo
    monitoreo.iniciar_sesion("run-001")
    monitoreo.registrar_evento({"evento": "paso_inicio", "paso": 1})
    resumen = monitoreo.consolidar_log(monitoreo.leer_log())
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

BASE = Path(__file__).resolve().parent
RUTA_LOG = BASE / "outputs" / "log_ejecucion.jsonl"

_ESTADOS = ("OK", "FALLBACK", "FALLIDO", "ABORTADO", "OMNIDO")
_TIPOS_ALERTA = {"alerta", "fallback_activado", "fallback_fallido", "timeout_real"}

_sesion: dict[str, Any] = {
    "run_id": None,
    "nivel_minimo": "INFO",
    "secuencia": 0,
}


# --------------------------------------------------------------------------- #
# Sesión y escritura
# --------------------------------------------------------------------------- #
def iniciar_sesion(run_id: str, nivel_minimo: str = "INFO") -> Path:
    """Arranca una sesión de monitoreo (run) y garantiza que exista outputs/.

    Args:
        run_id: identificador de la corrida, por ejemplo ``run-20260926-101500``.
        nivel_minimo: nivel mínimo a registrar (DEBUG, INFO, WARNING, ERROR).

    Returns:
        Ruta del archivo JSONL donde se anexan los eventos.
    """
    _sesion["run_id"] = run_id
    _sesion["nivel_minimo"] = nivel_minimo.upper()
    _sesion["secuencia"] = 0
    RUTA_LOG.parent.mkdir(parents=True, exist_ok=True)
    return RUTA_LOG


def ruta_log() -> Path:
    """Devuelve la ruta del log de ejecución."""
    return RUTA_LOG


def registrar_evento(evento: dict) -> dict:
    """Agrega metadatos al evento y lo anexa (append) al log JSONL.

    Args:
        evento: diccionario con al menos la clave ``evento``. Se le agregan
            ``run_id``, ``seq``, ``ts`` (ISO 8601) y ``nivel``.

    Returns:
        El evento ya enriquecido (igual al que se escribió en disco).
    """
    nivel = str(evento.get("nivel", "INFO")).upper()
    registro: dict[str, Any] = {
        "ts": datetime.now().astimezone().isoformat(timespec="milliseconds"),
        "run_id": _sesion["run_id"],
        "seq": _sesion["secuencia"],
        "nivel": nivel,
    }
    _sesion["secuencia"] += 1
    registro.update(evento)
    registro["nivel"] = nivel

    RUTA_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUTA_LOG.open("a", encoding="utf-8") as archivo:
        archivo.write(json.dumps(registro, ensure_ascii=False) + "\n")
    return registro


def _filtrar(eventos: Iterable[dict], run_id: str | None) -> list[dict]:
    """Filtra eventos por run_id (None = todos)."""
    lista = [e for e in eventos if isinstance(e, dict)]
    if run_id is None:
        return lista
    return [e for e in lista if e.get("run_id") == run_id]


def leer_log(ruta: Path | None = None, run_id: str | None = None) -> list[dict]:
    """Lee el log JSONL completo (o el de una corrida) ignorando líneas corruptas."""
    destino = Path(ruta) if ruta else RUTA_LOG
    if not destino.exists():
        return []
    eventos: list[dict] = []
    with destino.open("r", encoding="utf-8") as archivo:
        for linea in archivo:
            linea = linea.strip()
            if not linea:
                continue
            try:
                eventos.append(json.loads(linea))
            except json.JSONDecodeError:
                continue
    return _filtrar(eventos, run_id)


# --------------------------------------------------------------------------- #
# Consolidación
# --------------------------------------------------------------------------- #
def consolidar_log(eventos: list[dict]) -> dict:
    """Resume el log en métricas agregadas por paso, por evento y por agente.

    Args:
        eventos: lista de eventos (por ejemplo, ``leer_log()``).

    Returns:
        Diccionario con totales, ``por_paso``, ``alertas`` y duración lógica.
    """
    por_evento: Counter = Counter()
    por_paso: dict[int, dict] = {}
    alertas: list[dict] = []
    duracion = 0.0

    for evento in eventos:
        nombre = evento.get("evento", "?")
        por_evento[nombre] += 1
        if nombre in _TIPOS_ALERTA:
            alertas.append(evento)
        if "t_logico_s" in evento:
            duracion = max(duracion, float(evento["t_logico_s"]))

        paso_id = evento.get("paso")
        if paso_id is None:
            continue
        clave = int(paso_id)
        ficha = por_paso.setdefault(
            clave,
            {
                "paso": clave,
                "nombre": evento.get("nombre_paso", f"paso_{clave}"),
                "agente": evento.get("agente"),
                "estado": "OMNIDO",
                "intentos": 0,
                "reintentos": 0,
                "errores": [],
                "fallback": None,
                "inicio_s": None,
                "fin_s": None,
                "duracion_s": 0.0,
                "alertas": [],
            },
        )
        if evento.get("nombre_paso"):
            ficha["nombre"] = evento["nombre_paso"]
        if evento.get("agente"):
            ficha["agente"] = evento["agente"]

        if nombre == "paso_inicio":
            ficha["inicio_s"] = float(evento.get("t_logico_s", 0.0))
        elif nombre == "intento_ok":
            ficha["intentos"] += 1
        elif nombre == "intento_fallo":
            ficha["intentos"] += 1
            if ficha["intentos"] > 1:
                ficha["reintentos"] += 1
            ficha["errores"].append(
                {
                    "intento": evento.get("intento"),
                    "codigo": evento.get("codigo"),
                    "mensaje": evento.get("mensaje"),
                    "reintentable": evento.get("reintentable"),
                }
            )
        elif nombre == "fallback_activado":
            ficha["fallback"] = evento.get("agente_fallback")
        elif nombre == "paso_fin":
            ficha["estado"] = evento.get("estado", ficha["estado"])
            ficha["fin_s"] = float(evento.get("t_logico_s", ficha["inicio_s"] or 0.0))
            if ficha["inicio_s"] is not None:
                ficha["duracion_s"] = round(ficha["fin_s"] - ficha["inicio_s"], 3)
        if evento.get("nivel") in {"WARNING", "ERROR"}:
            ficha["alertas"].append(evento.get("mensaje", evento.get("evento")))

    pasos = [por_paso[k] for k in sorted(por_paso)]
    estados = Counter(p["estado"] for p in pasos)
    return {
        "eventos_total": len(eventos),
        "por_evento": dict(por_evento),
        "pasos": pasos,
        "pasos_total": len(pasos),
        "por_estado": {estado: estados.get(estado, 0) for estado in _ESTADOS},
        "intentos_total": sum(p["intentos"] for p in pasos),
        "reintentos_total": sum(p["reintentos"] for p in pasos),
        "pasos_con_fallback": sum(1 for p in pasos if p["fallback"]),
        "pasos_fallidos": estados.get("FALLIDO", 0) + estados.get("ABORTADO", 0),
        "alertas": alertas,
        "duracion_logica_s": round(duracion, 3),
    }


def resumir_log(eventos: list[dict], tope: int = 12) -> str:
    """Devuelve un resumen textual corto del log (útil para consola o alertas)."""
    resumen = consolidar_log(eventos)
    lineas = [
        f"eventos={resumen['eventos_total']} "
        f"pasos={resumen['pasos_total']} "
        f"intentos={resumen['intentos_total']} "
        f"reintentos={resumen['reintentos_total']} "
        f"fallbacks={resumen['pasos_con_fallback']} "
        f"fallidos={resumen['pasos_fallidos']} "
        f"alertas={len(resumen['alertas'])}"
    ]
    for evento in resumen["alertas"][:tope]:
        lineas.append(f"  [{evento.get('nivel')}] {evento.get('mensaje', evento)}")
    return "\n".join(lineas)


def escribir_json(datos: Any, ruta: Path) -> Path:
    """Escribe un objeto como JSON legible (UTF-8) creando la carpeta destino."""
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8") as archivo:
        json.dump(datos, archivo, ensure_ascii=False, indent=2)
    return ruta
