"""Orquestador multi-agente: ejecuta el proceso de pedidos con robustez.

Punto de entrada del proyecto. Hace cinco cosas:

1. Carga ``config.json`` (tarea, agentes, política de reintentos, fallbacks).
2. Construye los agentes y el contexto del pedido.
3. Ejecuta cada paso a través de :mod:`manejo_errores` (reintentos + backoff +
   fallback) registrando cada evento en el log JSONL (:mod:`monitoreo`).
4. Aplica los puntos de control: si un paso crítico queda FALLIDO aborta el
   proceso y deja los pasos siguientes en OMNIDO.
5. Genera el reporte Markdown y el diagrama de monitoreo en ``outputs/``.

Reproducible: la semilla fija (42) garantiza la misma corrida en cada
ejecución. Corre 100% offline con la stdlib de Python + matplotlib para el
gráfico.

Uso:
    python orquestador.py
"""

from __future__ import annotations

import json
import random
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable

# Consolas Windows sin UTF-8 (cp1252) no pueden imprimir símbolos como ✗/✓/→.
# Reconfiturar con errors="replace" evita el crash: el símbolo sale como "?".
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

import agentes as mod_agentes  # noqa: E402
import monitoreo  # noqa: E402
from manejo_errores import (  # noqa: E402
    RelojLogico,
    ResultadoReintento,
    ejecutar_con_fallback,
)

BASE = Path(__file__).resolve().parent
RUTA_CONFIG = BASE / "config.json"
RUTA_REPORTE = BASE / "outputs" / "reporte_ejecucion.md"
RUTA_DIAGRAMA = BASE / "outputs" / "diagrama_pasos.png"

COLOR_ESTADO = {"OK": "#2E9E5B", "FALLBACK": "#E1A33C", "FALLIDO": "#C0392B", "ABORTADO": "#7B241C"}


# --------------------------------------------------------------------------- #
# Configuración y contexto
# --------------------------------------------------------------------------- #
def cargar_config(ruta: Path | None = None) -> dict:
    """Carga ``config.json`` y valida los campos indispensables."""
    destino = Path(ruta) if ruta else RUTA_CONFIG
    with destino.open("r", encoding="utf-8") as archivo:
        config = json.load(archivo)
    for clave in ("tarea", "reintentos", "agentes", "monitoreo"):
        if clave not in config:
            raise KeyError(f"config.json incompleto: falta la clave '{clave}'")
    if not config["tarea"].get("pasos"):
        raise ValueError("config.json: la tarea no define pasos")
    return config


def construir_contexto(config: dict, reloj: RelojLogico) -> dict:
    """Arma el contexto del pedido a partir de ``tarea.contexto``."""
    tarea = config["tarea"]
    contexto = dict(tarea.get("contexto", {}))
    contexto["reloj"] = reloj
    contexto["stock"] = contexto.get("stock_inicial", 0)
    contexto.setdefault("domicilio_ok", True)
    contexto.setdefault("contacto_ok", True)
    return contexto


def rutas_de_monitoreo(config: dict) -> dict[str, Path]:
    """Resuelve las rutas de salidas declaradas en ``config.monitoreo``."""
    declared = config["monitoreo"]
    return {
        "log": BASE / declared.get("log", "outputs/log_ejecucion.jsonl"),
        "reporte": BASE / declared.get("reporte", "outputs/reporte_ejecucion.md"),
        "diagrama": BASE / declared.get("diagrama", "outputs/diagrama_pasos.png"),
    }


# --------------------------------------------------------------------------- #
# Ejecución de un paso
# --------------------------------------------------------------------------- #
def ejecutar_paso(
    paso: dict,
    registro_agentes: dict[str, mod_agentes.Agente],
    contexto: dict,
    config: dict,
    rng: random.Random,
    reloj: RelojLogico,
) -> ResultadoReintento:
    """Ejecuta un paso con reintentos, backoff y fallback configurado.

    Construye la ``accion`` primaria (agente del paso) y la ``accion_fallback``
    (agente de respaldo) y las entrega a :func:`manejo_errores.ejecutar_con_fallback`.
    """
    politica = config["reintentos"]
    simulacion = config.get("simulacion", {})
    paso_id = int(paso["id"])
    nombre = paso["nombre"]
    agente = registro_agentes[paso["agente"]]
    inicio_s = reloj.ahora()

    monitoreo.registrar_evento(
        {
            "evento": "paso_inicio",
            "paso": paso_id,
            "nombre_paso": nombre,
            "agente": agente.nombre,
            "descripcion": paso.get("descripcion", ""),
            "punto_control": paso.get("punto_control", ""),
            "max_reintentos": politica["max_reintentos"],
            "backoff_base": politica["backoff_base"],
            "t_logico_s": round(inicio_s, 3),
        }
    )

    def accion(_numero_intento: int) -> dict:
        """Invoca al agente del paso (un intento)."""
        return _accion_de_agente(agente, contexto)

    fallback_cfg = paso.get("fallback")
    accion_fallback: Callable[[int], dict] | None = None
    nombre_fallback = None
    if fallback_cfg:
        nombre_fallback = fallback_cfg["agente"]
        agente_fallback = registro_agentes[nombre_fallback]
        accion_fallback = lambda numero: _accion_de_agente(agente_fallback, contexto)  # noqa: E731

    resultado = ejecutar_con_fallback(
        accion,
        nombre_paso=nombre,
        paso_id=paso_id,
        agente=agente.nombre,
        max_reintentos=politica["max_reintentos"],
        backoff_base=politica["backoff_base"],
        factor=politica.get("factor", 2.0),
        jitter=politica.get("jitter", 0.0),
        accion_fallback=accion_fallback,
        nombre_fallback=nombre_fallback,
        max_reintentos_fallback=politica.get("max_reintentos_fallback", 2),
        rng=rng,
        contexto=contexto,
        escala_tiempo=politica.get("escala_tiempo_real", 1.0),
        dormir=simulacion.get("dormir_entre_reintentos", True),
        solo_reintentables=politica.get("solo_errores_reintentables", True),
    )
    reloj.avanzar(0.05)

    if resultado.estado == "FALLIDO":
        alertas(resultado, paso, nombre, agente)
    if resultado.estado == "FALLBACK" and fallback_cfg:
        alertas_fallback(resultado, paso, nombre, nombre_fallback)

    fin_s = reloj.ahora()
    monitoreo.registrar_evento(
        {
            "evento": "paso_fin",
            "paso": paso_id,
            "nombre_paso": nombre,
            "agente": agente.nombre,
            "estado": resultado.estado,
            "intentos": resultado.total_intentos,
            "reintentos": resultado.reintentos,
            "agente_fallback": nombre_fallback if resultado.fallback_usado else None,
            "detalle": _detalle_de_salida(resultado),
            "duracion_logica_s": round(fin_s - inicio_s, 3),
            "t_logico_s": round(fin_s, 3),
            "nivel": "ERROR" if resultado.estado in {"FALLIDO", "ABORTADO"} else "INFO",
        }
    )
    return resultado


def _accion_de_agente(agente: mod_agentes.Agente, contexto: dict) -> dict:
    """Ejecuta un agente y propaga el error si la herramienta falló."""
    salida = mod_agentes.ejecutar_agente(agente, contexto)
    if not salida["ok"]:
        raise salida["error"]
    return salida["salida"]


def _detalle_de_salida(resultado: ResultadoReintento) -> str:
    """Extrae el detalle legible de la salida del agente."""
    if not resultado.ok or not resultado.resultado:
        return resultado.ultimo_error.mensaje if resultado.ultimo_error else "sin detalle"
    return str(resultado.resultado.get("detalle", resultado.resultado.get("accion", "")))


def _plural(cantidad: int, palabra: str) -> str:
    """Pluraliza una palabra: ``_plural(1, 'intento')`` → ``'1 intento'``."""
    return f"{cantidad} {palabra}" if cantidad == 1 else f"{cantidad} {palabra}s"


def _describir_alerta(evento: dict) -> str:
    """Texto legible de un evento de nivel WARNING/ERROR (con o sin ``mensaje``)."""
    if evento.get("mensaje"):
        return str(evento["mensaje"])
    if evento.get("evento") == "paso_fin":
        return (
            f"el paso '{evento.get('nombre_paso')}' terminó en estado "
            f"{evento.get('estado')} tras {evento.get('intentos')} intentos"
        )
    return f"evento '{evento.get('evento')}' en {evento.get('agente')}"


def alertas(resultado: ResultadoReintento, paso: dict, nombre: str, agente: mod_agentes.Agente) -> None:
    """Registra una alerta cuando un paso termina FALLIDO."""
    codigo = resultado.ultimo_error.codigo if resultado.ultimo_error else "DESCONOCIDO"
    if paso.get("critico", True):
        mensaje = (
            f"paso crítico '{nombre}' falló ({codigo}) tras {resultado.total_intentos} intentos: "
            "el pedido queda frenado para revisión manual"
        )
    else:
        mensaje = (
            f"paso '{nombre}' falló ({codigo}) y no tiene fallback: "
            "el pedido sigue su curso pero requiere contacto manual con el cliente"
        )
    monitoreo.registrar_evento(
        {
            "evento": "alerta",
            "paso": paso["id"],
            "nombre_paso": nombre,
            "agente": agente.nombre,
            "nivel": "ERROR",
            "codigo": codigo,
            "mensaje": mensaje,
        }
    )
    resultado.alertas.append(mensaje)


def alertas_fallback(resultado: ResultadoReintento, paso: dict, nombre: str, nombre_fallback: str | None) -> None:
    """Registra la alerta informativa cuando se activa un fallback."""
    motivo = paso.get("fallback", {}).get("motivo", "sin motivo configurado")
    mensaje = f"paso '{nombre}' degradado a {nombre_fallback} (punto de control: {motivo})"
    monitoreo.registrar_evento(
        {
            "evento": "alerta",
            "paso": paso["id"],
            "nombre_paso": nombre,
            "agente": nombre_fallback,
            "nivel": "WARNING",
            "codigo": "FALLBACK_ACTIVADO",
            "mensaje": mensaje,
        }
    )
    resultado.alertas.append(mensaje)


# --------------------------------------------------------------------------- #
# Reporte y diagrama
# --------------------------------------------------------------------------- #
def generar_reporte(
    config: dict,
    resultados: list[dict],
    run_id: str,
    reloj: RelojLogico,
    resumen: dict,
    estado_final: str,
    destino: Path | None = None,
) -> Path:
    """Escribe el reporte Markdown de la corrida en ``outputs/reporte_ejecucion.md``.

    Incluye: encabezado, tabla de estados por paso, árbol de ejecución con los
    intentos, mapa de reintentos/fallbacks y el resumen de monitoreo.
    """
    destino = destino or RUTA_REPORTE
    destino.parent.mkdir(parents=True, exist_ok=True)
    politica = config["reintentos"]
    tarea = config["tarea"]

    lineas: list[str] = []
    lineas.append(f"# Reporte de ejecución — {tarea['nombre']}")
    lineas.append("")
    lineas.append(f"- **Estado del proceso**: **{estado_final}**")
    lineas.append(f"- **Corrida**: `{run_id}`")
    lineas.append(f"- **Fecha**: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    lineas.append(f"- **Pedido**: `{tarea['contexto'].get('pedido_id')}` — {tarea['contexto'].get('cliente')}")
    lineas.append(f"- **Semilla**: `{config['semilla']}` (corrida reproducible)")
    lineas.append(
        f"- **Política**: `max_reintentos={politica['max_reintentos']}`, "
        f"`backoff_base={politica['backoff_base']}`s, estrategia {politica.get('estrategia', 'exponencial')}"
    )
    lineas.append(
        f"- **Duración lógica**: {reloj.ahora():.2f} s (latencias y backoffs simulados)"
    )
    lineas.append("")

    lineas.append("## Estados por paso")
    lineas.append("")
    lineas.append("| # | Paso | Agente | Estado | Intentos | Reintentos | Duración (s) | Detalle |")
    lineas.append("|---|---|---|---|---|---|---|---|")
    for item in resultados:
        r: ResultadoReintento = item["resultado"]
        detalle = _detalle_de_salida(r).replace("|", "/")
        if r.fallback_usado:
            detalle = f"**fallback → {item['fallback']}** · {detalle}"
        lineas.append(
            f"| {item['paso']['id']} | `{item['paso']['nombre']}` | `{item['paso']['agente']}` | "
            f"**{r.estado}** | {_plural(r.total_intentos, 'intento')} | {r.reintentos} | "
            f"{item['duracion_s']:.2f} | {detalle} |"
        )
    lineas.append("")

    lineas.append("## Árbol de ejecución")
    lineas.append("")
    lineas.append("```text")
    lineas.append(arbol_de_ejecucion(resultados))
    lineas.append("```")
    lineas.append("")

    lineas.append("## Resumen de monitoreo")
    lineas.append("")
    for clave, (singular, plural) in (
        ("pasos_total", ("paso con estado", "pasos con estado")),
        ("intentos_total", ("intento total", "intentos totales")),
        ("reintentos_total", ("reintento", "reintentos")),
        ("pasos_con_fallback", ("paso con fallback", "pasos con fallback")),
        ("pasos_fallidos", ("paso fallido", "pasos fallidos")),
    ):
        cantidad = resumen[clave]
        lineas.append(f"- **{cantidad}** {singular if cantidad == 1 else plural}")
    eventos_corrida = resumen["eventos_total"]
    lineas.append(
        f"- **{eventos_corrida}** {'evento' if eventos_corrida == 1 else 'eventos'} "
        "en el log de la corrida"
    )
    if resumen["alertas"]:
        lineas.append("")
        lineas.append("### Alertas")
        for evento in resumen["alertas"]:
            lineas.append(
                f"- `{evento.get('nivel')}` [paso {evento.get('paso')}] {_describir_alerta(evento)}"
            )
    else:
        lineas.append("- Sin alertas en la corrida")
    lineas.append("")

    lineas.append("## Mapa de reintentos y fallbacks")
    lineas.append("")
    lineas.append("| Paso | Falla típica | Reintentos | Fallback |")
    lineas.append("|---|---|---|---|")
    mapa = {
        "validar_pago": ("pasarela caída / timeout del PSP", "—"),
        "actualizar_stock": ("ERP sin respuesta o 503", "`AgenteFallbackStock` (planilla manual + ticket)"),
        "preparar_envio": ("transportista lento o domicilio inválido", "—"),
        "notificar_cliente": ("proveedor de mensajería inestable", "— (se emite alerta y contacto manual)"),
    }
    for paso in tarea["pasos"]:
        falla, fallback = mapa.get(paso["nombre"], ("—", "—"))
        lineas.append(
            f"| {paso['id']}. {paso['nombre']} | {falla} | hasta {politica['max_reintentos']} "
            f"intentos (backoff {politica['backoff_base']}s ×{politica.get('factor', 2)}) | {fallback} |"
        )
    lineas.append("")
    lineas.append(
        "Log completo (append) en `outputs/log_ejecucion.jsonl`; "
        "diagrama en `outputs/diagrama_pasos.png`."
    )
    lineas.append("")

    destino.write_text("\n".join(lineas), encoding="utf-8")
    return destino


def arbol_de_ejecucion(resultados: list[dict]) -> str:
    """Construye el árbol textual de la ejecución (intentos + fallback)."""
    lineas = ["pedido " + str(resultados[0]["contexto"].get("pedido_id", ""))]
    for item in resultados:
        paso = item["paso"]
        r: ResultadoReintento = item["resultado"]
        prefijo = "└─" if item is resultados[-1] else "├─"
        lineas.append(
            f"{prefijo} [{paso['id']}] {paso['nombre']}  ({r.estado} · {item['duracion_s']:.2f}s · "
            f"{_plural(r.total_intentos, 'intento')})"
        )
        conector = "   " if prefijo == "└─" else "│  "
        for intento in r.intentos:
            marca = "✓" if intento.ok else "✗"
            extra = f" · espera {intento.espera_siguiente_s:.2f}s" if intento.espera_siguiente_s else ""
            texto = intento.mensaje or "OK"
            if intento.codigo:
                texto = f"{intento.codigo} — {texto}"
            lineas.append(f"{conector}  {marca} intento {intento.numero}: {texto}{extra}")
        if r.fallback_usado:
            lineas.append(f"{conector}  ⚠ FALLBACK → {item['fallback']} ({item['motivo_fallback']})")
            for intento in r.fallback_intentos:
                marca = "✓" if intento.ok else "✗"
                texto = intento.mensaje or "OK"
                if intento.codigo:
                    texto = f"{intento.codigo} — {texto}"
                lineas.append(f"{conector}    {marca} intento {intento.numero}: {texto}")
        if r.estado == "OMNIDO":
            lineas.append(f"{conector}  · paso omitido (proceso abortado en un punto de control previo)")
    return "\n".join(lineas)


def generar_diagrama(
    resultados: list[dict],
    reloj: RelojLogico,
    run_id: str,
    destino: Path | None = None,
) -> Path:
    """Dibuja la línea de tiempo de los pasos (Gantt) con su estado final.

    Eje X: segundos lógicos desde el inicio de la corrida (latencias + backoffs
    simulados). Eje Y: pasos. Color: OK / FALLBACK / FALLIDO / ABORTADO.
    Las barras con trama indican que el paso pasó por reintentos; las cruces
    marcan el instante lógico de cada intento fallido y la línea punteada, el
    momento en que se activó el fallback.
    """
    destino = destino or RUTA_DIAGRAMA
    destino.parent.mkdir(parents=True, exist_ok=True)

    filas = [item for item in resultados if item["resultado"].estado != "OMNIDO"]
    altura = max(3.2, 0.9 * len(filas) + 2.2)
    fig, ax = plt.subplots(figsize=(11, altura))

    for indice, item in enumerate(filas):
        r: ResultadoReintento = item["resultado"]
        y = len(filas) - indice - 1
        ancho = max(0.12, item["fin_s"] - item["inicio_s"])
        estado = r.estado if r.estado in COLOR_ESTADO else "FALLIDO"
        color = COLOR_ESTADO[estado]
        ax.barh(
            y,
            ancho,
            left=item["inicio_s"],
            height=0.55,
            color=color,
            alpha=0.9,
            edgecolor="black",
            linewidth=0.6,
            hatch="//" if r.reintentos else None,
        )
        etiqueta = f"{r.estado} · {_plural(r.total_intentos, 'intento')}"
        if r.fallback_usado:
            etiqueta = f"FALLBACK ({_plural(r.total_intentos, 'intento')}) → {item['fallback']}"
        ax.text(
            item["inicio_s"] + ancho + 0.08,
            y,
            etiqueta,
            va="center",
            ha="left",
            fontsize=8.5,
        )
        for intento in r.intentos:
            if intento.codigo:
                ax.plot(
                    [intento.t_logico_s],
                    [y],
                    marker="x",
                    color="white",
                    markersize=7,
                    markeredgewidth=1.6,
                )
        if r.fallback_usado and r.fallback_intentos:
            ax.plot(
                [r.fallback_intentos[0].t_logico_s] * 2,
                [y - 0.3, y + 0.3],
                color="#7D6608",
                linewidth=1.8,
                linestyle=":",
            )

    ax.set_yticks(range(len(filas)))
    ax.set_yticklabels(
        [f"[{item['paso']['id']}] {item['paso']['nombre']}" for item in reversed(filas)],
        fontsize=9,
    )
    ax.set_xlabel("tiempo lógico desde el inicio (s) — latencias + backoff simulados", fontsize=9)
    ax.set_title(
        f"Monitoreo del proceso por agentes · corrida {run_id}\n"
        f"{len([i for i in filas if i['resultado'].estado == 'OK'])} OK · "
        f"{len([i for i in filas if i['resultado'].estado == 'FALLBACK'])} fallback · "
        f"{len([i for i in filas if i['resultado'].estado in {'FALLIDO', 'ABORTADO'}])} fallidos",
        fontsize=10,
    )
    ax.grid(axis="x", linestyle=":", alpha=0.4)
    ax.set_axisbelow(True)
    ax.set_xlim(0, max(2.0, reloj.ahora() * 1.35))
    ax.legend(
        handles=[
            Patch(facecolor=COLOR_ESTADO["OK"], label="OK"),
            Patch(facecolor=COLOR_ESTADO["FALLBACK"], label="FALLBACK (degradado)"),
            Patch(facecolor=COLOR_ESTADO["FALLIDO"], label="FALLIDO"),
            Patch(facecolor="#FFFFFF", edgecolor="black", hatch="//", label="pasó por reintentos"),
            Line2D([], [], color="black", marker="x", linestyle="", label="intento fallido"),
            Line2D([], [], color="#7D6608", linestyle=":", linewidth=1.8, label="activación del fallback"),
        ],
        loc="lower right",
        fontsize=8,
        frameon=True,
    )
    fig.tight_layout()
    fig.savefig(destino, dpi=150)
    plt.close(fig)
    return destino


# --------------------------------------------------------------------------- #
# Orquestación
# --------------------------------------------------------------------------- #
def orquestar(
    config: dict, rng: random.Random, verboso: bool = True
) -> tuple[list[dict], RelojLogico, str]:
    """Ejecuta el proceso completo, paso por paso, aplicando los puntos de control.

    Returns:
        ``(resultados, reloj, estado_proceso)`` donde ``estado_proceso`` es
        ``COMPLETADO``, ``COMPLETADO_CON_ALERTAS`` o ``ABORTADO``.
    """
    reloj = RelojLogico()
    registro_agentes = mod_agentes.construir_agentes(config, rng)
    contexto = construir_contexto(config, reloj)
    pasos = config["tarea"]["pasos"]
    resultados: list[dict] = []
    abortar = False

    for indice, paso in enumerate(pasos, start=1):
        if abortar:
            resultados.append(
                {
                    "paso": paso,
                    "resultado": ResultadoReintento(ok=False, estado="OMNIDO"),
                    "inicio_s": reloj.ahora(),
                    "fin_s": reloj.ahora(),
                    "duracion_s": 0.0,
                    "contexto": contexto,
                    "fallback": None,
                    "motivo_fallback": None,
                }
            )
            if verboso:
                print(f"[{indice}/{len(pasos)}] {paso['nombre']:<18} OMITIDO (proceso abortado)")
            continue

        if verboso:
            agente = registro_agentes[paso["agente"]]
            print(
                f"[{indice}/{len(pasos)}] {paso['nombre']:<18} agente={agente.nombre} "
                f"max_reintentos={config['reintentos']['max_reintentos']} "
                f"backoff_base={config['reintentos']['backoff_base']}s"
            )

        inicio_s = reloj.ahora()
        resultado = ejecutar_paso(paso, registro_agentes, contexto, config, rng, reloj)
        fin_s = reloj.ahora()
        if verboso:
            _imprimir_paso(resultado, inicio_s, fin_s)
        resultados.append(
            {
                "paso": paso,
                "resultado": resultado,
                "inicio_s": inicio_s,
                "fin_s": fin_s,
                "duracion_s": fin_s - inicio_s,
                "contexto": contexto,
                "fallback": (paso.get("fallback") or {}).get("agente"),
                "motivo_fallback": (paso.get("fallback") or {}).get("motivo"),
            }
        )
        if resultado.estado == "FALLIDO" and paso.get("critico", True):
            abortar = True
            if verboso:
                print(
                    f"    ⛔ punto de control: '{paso['nombre']}' es crítico y quedó FALLIDO → "
                    "se aborta el proceso"
                )

    if abortar:
        estado = "ABORTADO"
    elif any(item["resultado"].estado == "FALLIDO" for item in resultados):
        estado = "COMPLETADO_CON_ALERTAS"
    else:
        estado = "COMPLETADO"
    return resultados, reloj, estado


def _imprimir_paso(resultado: ResultadoReintento, inicio_s: float, fin_s: float) -> None:
    """Imprime el detalle de intentos, backoffs y fallback de un paso."""
    for intento in resultado.intentos:
        if intento.ok:
            print(
                f"    ✓ intento {intento.numero}: OK "
                f"({intento.latencia_sim_ms:.0f} ms simulados, t={intento.t_logico_s:.2f}s)"
            )
        else:
            print(
                f"    ✗ intento {intento.numero}: {intento.codigo} — {intento.mensaje} "
                f"(t={intento.t_logico_s:.2f}s)"
            )
            if intento.espera_siguiente_s:
                print(
                    f"      ↻ backoff: espera {intento.espera_siguiente_s:.2f}s "
                    f"antes del reintento (exponencial + jitter)"
                )
    if resultado.fallback_usado:
        print("    ⚠ FALLBACK ACTIVADO: el agente principal agotó los reintentos")
        for intento in resultado.fallback_intentos:
            marca = "✓" if intento.ok else "✗"
            print(f"      {marca} respaldo intento {intento.numero}: {intento.mensaje or 'OK'}")
    for alerta in resultado.alertas:
        resumen_alerta = alerta if len(alerta) <= 110 else alerta[:107] + "..."
        print(f"    ! {resumen_alerta}")
    print(
        f"    → estado {resultado.estado} | {_plural(resultado.total_intentos, 'intento')} "
        f"| duración lógica {fin_s - inicio_s:.2f}s"
    )


def main() -> int:
    """Punto de entrada: corre el proceso completo y genera los artefactos."""
    config = cargar_config()
    random.seed(config["semilla"])
    rng = random.Random(config["semilla"])
    rutas = rutas_de_monitoreo(config)
    for ruta in rutas.values():
        ruta.parent.mkdir(parents=True, exist_ok=True)
    run_id = f"run-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    monitoreo.iniciar_sesion(run_id, config["monitoreo"].get("nivel_minimo", "INFO"))

    tarea = config["tarea"]
    print("=" * 78)
    print(f"ORQUESTADOR DE AGENTES · {tarea['nombre']}")
    print("=" * 78)
    print(f"pedido {tarea['contexto'].get('pedido_id')} · cliente {tarea['contexto'].get('cliente')}")
    print(f"corrida {run_id} · semilla {config['semilla']} · {len(tarea['pasos'])} pasos")

    monitoreo.registrar_evento(
        {
            "evento": "run_inicio",
            "proyecto": config.get("nombre_proyecto"),
            "tarea": tarea["id"],
            "semilla": config["semilla"],
            "pasos": len(tarea["pasos"]),
            "politica": config["reintentos"],
        }
    )

    resultados, reloj, estado_final = orquestar(config, rng)

    eventos = monitoreo.leer_log(run_id=run_id)
    resumen = monitoreo.consolidar_log(eventos)
    reporte = generar_reporte(config, resultados, run_id, reloj, resumen, estado_final, rutas["reporte"])
    diagrama = generar_diagrama(resultados, reloj, run_id, rutas["diagrama"])

    total_eventos = len(monitoreo.leer_log()) + 1  # +1: el run_fin que se registra abajo
    monitoreo.registrar_evento(
        {
            "evento": "run_fin",
            "estado": estado_final,
            "eventos_corrida": len(eventos),
            "pasos_ok": resumen["por_estado"]["OK"],
            "pasos_fallback": resumen["por_estado"]["FALLBACK"],
            "pasos_fallidos": resumen["pasos_fallidos"],
            "intentos": resumen["intentos_total"],
            "reintentos": resumen["reintentos_total"],
            "alertas": len(resumen["alertas"]),
            "duracion_logica_s": round(reloj.ahora(), 2),
        }
    )

    print("-" * 78)
    print(f"resumen: {resumen['por_estado']['OK']} OK · {resumen['por_estado']['FALLBACK']} fallback · "
          f"{resumen['pasos_fallidos']} fallidos · {resumen['intentos_total']} intentos "
          f"({resumen['reintentos_total']} reintentos) · {len(eventos)} eventos")
    print(f"estado del proceso: {estado_final}")
    print(f"log      → {rutas['log'].relative_to(BASE)} ({total_eventos} eventos acumulados)")
    print(f"reporte  → {reporte.relative_to(BASE)}")
    print(f"diagrama → {diagrama.relative_to(BASE)}")
    return 0 if estado_final != "ABORTADO" else 1


if __name__ == "__main__":
    raise SystemExit(main())
