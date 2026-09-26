"""Manejo de errores: reintentos con backoff exponencial, timeout y fallback.

Este módulo es el corazón de la robustez del orquestador y **no depende de los
agentes simulados**: recibe cualquier ``accion`` (una función que puede fallar)
y la envuelve con una política de reintentos + degradación. En producción la
misma función se usa envolviendo llamadas HTTP, queries SQL o mensajes de cola.

Políticas implementadas:
    * ``reintentar``            → N intentos con backoff exponencial + jitter.
    * ``ejecutar_con_fallback``  → si se agotan los reintentos y hay agente de
      respaldo, lo ejecuta (con su propio presupuesto de reintentos) y marca el
      paso como FALLBACK; si tampoco funciona el paso queda FALLIDO.
    * Errores tipados (``ErrorAgente``) con flag ``reintentable``: un rechazo de
      negocio (pago rechazado) no se reintenta aunque queden intentos.
    * Timeout: en el demo lo dispara el agente simulado
      (``ErrorTimeoutAgente``); con herramientas reales se reemplaza por el
      timeout de la llamada (HTTP, SDK, ``future.result(timeout=...)``).

Uso:
    from manejo_errores import ejecutar_con_fallback
    resultado = ejecutar_con_fallback(
        accion, accion_fallback=respaldo, nombre_paso="actualizar_stock",
        paso_id=2, agente="AgenteActualizarStock", max_reintentos=3,
        backoff_base=1.0,
    )
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import monitoreo


class ErrorAgente(RuntimeError):
    """Error de herramienta MODELADO como reintentable o no reintentable.

    Attributes:
        codigo: identificador corto del error (ej. ``TIMEOUT_ERP``).
        reintentable: si True la política insiste; si False el paso se aborta en
            el acto (ej. pago rechazado, dirección inválida).
        herramienta: nombre de la herramienta simulada que falló.
    """

    def __init__(
        self,
        codigo: str,
        mensaje: str,
        *,
        reintentable: bool = True,
        herramienta: str = "",
        latencia_sim_ms: float = 0.0,
    ) -> None:
        super().__init__(f"[{codigo}] {mensaje}")
        self.codigo = codigo
        self.mensaje = mensaje
        self.reintentable = reintentable
        self.herramienta = herramienta
        self.latencia_sim_ms = float(latencia_sim_ms)


class ErrorTimeoutAgente(ErrorAgente):
    """La herramienta no respondió dentro del timeout (simulado o real)."""


class RelojLogico:
    """Reloj de tiempo *simulado* usado por el reporte y el diagrama.

    Medir con el reloj real haría el gráfico ilegible (todo dura milisegundos).
    Este reloj acumula segundos lógicos: latencia simulada de cada intento +
    esperas de backoff. Es determinista y reproduce la línea de tiempo real del
    proceso aunque el demo comprima las esperas con ``escala_tiempo``.
    """

    def __init__(self, inicio: float = 0.0) -> None:
        self.t = float(inicio)

    def avanzar(self, segundos: float) -> float:
        """Suma ``segundos`` al reloj lógico y devuelve el valor actual."""
        self.t += max(0.0, float(segundos))
        return self.t

    def ahora(self) -> float:
        """Devuelve el tiempo lógico acumulado en segundos."""
        return self.t


def _tick(reloj: RelojLogico | None) -> float | None:
    """Instante del reloj lógico redondeado (para el log y los reportes)."""
    return round(reloj.ahora(), 3) if reloj is not None else None


@dataclass
class Intento:
    """Registro de un intento de ejecución (exitoso o fallido)."""

    numero: int
    ok: bool
    codigo: str | None = None
    mensaje: str | None = None
    reintentable: bool = True
    latencia_sim_ms: float = 0.0
    duracion_real_ms: float = 0.0
    t_logico_s: float = 0.0
    espera_siguiente_s: float = 0.0

    def resumen(self) -> str:
        """Texto de una línea para la consola y el reporte."""
        if self.ok:
            return f"intento {self.numero} → OK ({self.latencia_sim_ms:.0f} ms simulados)"
        return f"intento {self.numero} → FALLA {self.codigo} ({self.mensaje})"


@dataclass
class ResultadoReintento:
    """Resultado crudo de ``reintentar`` / ``ejecutar_con_fallback``."""

    ok: bool
    estado: str = "OK"
    intentos: list[Intento] = field(default_factory=list)
    resultado: dict | None = None
    fallback_usado: bool = False
    fallback_intentos: list[Intento] = field(default_factory=list)
    ultimo_error: ErrorAgente | None = None
    alertas: list[str] = field(default_factory=list)

    @property
    def total_intentos(self) -> int:
        """Cantidad total de intentos, incluye los del agente de respaldo."""
        return len(self.intentos) + len(self.fallback_intentos)

    @property
    def reintentos(self) -> int:
        """Cantidad de reintentos (intentos que no fueron el primero)."""
        return max(0, len(self.intentos) - 1) + max(0, len(self.fallback_intentos) - 1)


def calcular_backoff(
    intento: int,
    backoff_base: float = 1.0,
    factor: float = 2.0,
    jitter: float = 0.2,
    rng: random.Random | None = None,
) -> float:
    """Devuelve la espera (segundos lógicos) antes del reintento ``intento``.

    ``espera = backoff_base * factor ** (intento - 1) * (1 +- jitter)``

    El jitter evita que varios agentes reintenten en el mismo milisegundo
    (thundering herd) contra un servicio que recién se está recuperando.
    """
    base = max(0.0, float(backoff_base)) * (max(1.0, float(factor)) ** max(0, intento - 1))
    if jitter and rng is not None:
        base *= 1.0 + rng.uniform(-jitter, jitter)
    return round(max(0.0, base), 3)


def _dormir(segundos_logicos: float, escala: float, activo: bool) -> None:
    """Duerme ``segundos_logicos * escala`` (el demo comprime el tiempo real)."""
    if activo and escala > 0 and segundos_logicos > 0:
        time.sleep(segundos_logicos * escala)


def reintentar(
    accion: Callable[[int], dict],
    max_reintentos: int = 3,
    backoff_base: float = 1.0,
    on_fallback: Callable[[dict], dict | None] | None = None,
    *,
    factor: float = 2.0,
    jitter: float = 0.2,
    rng: random.Random | None = None,
    contexto: dict | None = None,
    escala_tiempo: float = 1.0,
    dormir: bool = True,
    solo_reintentables: bool = True,
) -> ResultadoReintento:
    """Ejecuta ``accion`` con reintentos y backoff exponencial.

    Args:
        accion: ``accion(numero_intento) -> dict``. Si devuelve un dict el
            intento es exitoso; si lanza ``ErrorAgente`` (o cualquier excepción)
            el intento se considera fallido y queda registrado en el log.
        max_reintentos: total de intentos permitidos (1 original + N-1
            reintentos). ``max_reintentos=3`` → hasta 3 llamadas.
        backoff_base: espera base en segundos para el primer reintento.
        on_fallback: callback invocado al agotar los reintentos. Recibe un dict
            con el motivo del fallo y devuelve el dict del resultado del
            respaldo, o ``None`` si el fallback no aplica.
        factor: multiplicador del backoff exponencial.
        jitter: variabilidad relativa de la espera.
        rng: generador para el jitter (reproducibilidad con semilla fija).
        contexto: contexto del paso; puede incluir ``reloj`` (RelojLogico).
        escala_tiempo: factor que comprime las esperas reales del demo.
        dormir: si False no se_duerme (útil para tests).
        solo_reintentables: si True corta la secuencia ante errores marcados como
            no reintentables (rechazo de negocio).

    Returns:
        ``ResultadoReintento`` con los intentos, el error final y, si ``on_fallback``
        tuvo éxito, ``estado="FALLBACK"``.
    """
    contexto = dict(contexto or {})
    reloj: RelojLogico | None = contexto.get("reloj")
    intentos: list[Intento] = []
    ultimo_error: ErrorAgente | None = None

    for numero in range(1, max(1, int(max_reintentos)) + 1):
        if numero > 1:
            espera = calcular_backoff(numero - 1, backoff_base, factor, jitter, rng)
            if reloj:
                reloj.avanzar(espera)
            _dormir(espera, escala_tiempo, dormir)
            if intentos:
                intentos[-1].espera_siguiente_s = espera
            monitoreo.registrar_evento(
                {
                    "evento": "espera_backoff",
                    "paso": contexto.get("paso"),
                    "nombre_paso": contexto.get("nombre_paso"),
                    "agente": contexto.get("agente"),
                    "intento": numero,
                    "espera_s": espera,
                    "estrategia": "exponencial",
                    "t_logico_s": _tick(reloj),
                }
            )

        inicio_real = time.perf_counter()
        try:
            salida = accion(numero)
        except ErrorAgente as error:
            duracion_real_ms = (time.perf_counter() - inicio_real) * 1000
            ultimo_error = error
            intento = Intento(
                numero=numero,
                ok=False,
                codigo=error.codigo,
                mensaje=error.mensaje,
                reintentable=error.reintentable,
                latencia_sim_ms=error.latencia_sim_ms,
                duracion_real_ms=round(duracion_real_ms, 1),
                t_logico_s=_tick(reloj) or 0.0,
            )
            intentos.append(intento)
            monitoreo.registrar_evento(
                {
                    "evento": "intento_fallo",
                    "paso": contexto.get("paso"),
                    "nombre_paso": contexto.get("nombre_paso"),
                    "agente": contexto.get("agente"),
                    "intento": numero,
                    "codigo": error.codigo,
                    "mensaje": error.mensaje,
                    "reintentable": error.reintentable,
                    "herramienta": error.herramienta,
                    "duracion_real_ms": intento.duracion_real_ms,
                    "t_logico_s": intento.t_logico_s,
                }
            )
            if solo_reintentables and not error.reintentable:
                return ResultadoReintento(
                    ok=False, estado="FALLIDO", intentos=intentos, ultimo_error=error
                )
        except Exception as error:  # defensivo: bug o excepción no tipada
            duracion_real_ms = (time.perf_counter() - inicio_real) * 1000
            intento = Intento(
                numero=numero,
                ok=False,
                codigo="EXCEPCION_NO_CONTROLADA",
                mensaje=f"{type(error).__name__}: {error}",
                reintentable=False,
                duracion_real_ms=round(duracion_real_ms, 1),
                t_logico_s=_tick(reloj) or 0.0,
            )
            intentos.append(intento)
            monitoreo.registrar_evento(
                {
                    "evento": "intento_fallo",
                    "paso": contexto.get("paso"),
                    "nombre_paso": contexto.get("nombre_paso"),
                    "agente": contexto.get("agente"),
                    "intento": numero,
                    "codigo": intento.codigo,
                    "mensaje": intento.mensaje,
                    "reintentable": False,
                    "nivel": "ERROR",
                    "duracion_real_ms": intento.duracion_real_ms,
                    "t_logico_s": intento.t_logico_s,
                }
            )
            return ResultadoReintento(
                ok=False,
                estado="FALLIDO",
                intentos=intentos,
                ultimo_error=ErrorAgente(intento.codigo or "ERROR", intento.mensaje or "", reintentable=False),
            )
        else:
            duracion_real_ms = (time.perf_counter() - inicio_real) * 1000
            intento = Intento(
                numero=numero,
                ok=True,
                duracion_real_ms=round(duracion_real_ms, 1),
                t_logico_s=_tick(reloj) or 0.0,
            )
            latencia = (salida or {}).get("latencia_sim_ms")
            if isinstance(latencia, (int, float)):
                intento.latencia_sim_ms = float(latencia)
            intentos.append(intento)
            monitoreo.registrar_evento(
                {
                    "evento": "intento_ok",
                    "paso": contexto.get("paso"),
                    "nombre_paso": contexto.get("nombre_paso"),
                    "agente": contexto.get("agente"),
                    "intento": numero,
                    "salida": salida,
                    "duracion_real_ms": intento.duracion_real_ms,
                    "t_logico_s": intento.t_logico_s,
                }
            )
            return ResultadoReintento(ok=True, estado="OK", intentos=intentos, resultado=salida)

    if on_fallback is not None:
        ultimo = intentos[-1] if intentos else None
        motivo = {
            "paso": contexto.get("paso"),
            "nombre_paso": contexto.get("nombre_paso"),
            "agente": contexto.get("agente"),
            "intentos": len(intentos),
            "codigo": ultimo.codigo if ultimo else None,
            "mensaje": ultimo.mensaje if ultimo else None,
            "t_logico_s": _tick(reloj),
        }
        salida_fallback = on_fallback(motivo)
        if salida_fallback:
            intentos_fb = salida_fallback.get("intentos_fallback") or []
            return ResultadoReintento(
                ok=True,
                estado="FALLBACK",
                intentos=intentos,
                resultado=salida_fallback,
                fallback_usado=True,
                fallback_intentos=list(intentos_fb),
                ultimo_error=ultimo_error,
            )

    return ResultadoReintento(
        ok=False, estado="FALLIDO", intentos=intentos, ultimo_error=ultimo_error
    )


def ejecutar_con_fallback(
    accion: Callable[[int], dict],
    *,
    nombre_paso: str,
    paso_id: int,
    agente: str,
    max_reintentos: int = 3,
    backoff_base: float = 1.0,
    accion_fallback: Callable[[int], dict] | None = None,
    nombre_fallback: str | None = None,
    max_reintentos_fallback: int = 2,
    factor: float = 2.0,
    jitter: float = 0.2,
    rng: random.Random | None = None,
    contexto: dict | None = None,
    escala_tiempo: float = 1.0,
    dormir: bool = True,
    solo_reintentables: bool = True,
    timeout_real_s: float | None = None,
) -> ResultadoReintento:
    """Ejecuta un paso con reintentos y, si falla, con el agente de respaldo.

    ``accion_fallback`` recibe el mismo ``(intento)`` que la acción principal y
    se ejecuta con su propio presupuesto de reintentos. Si el fallback tampoco
    funciona, el paso queda FALLIDO y le corresponde al orquestador decidir si
    aborta el proceso (según el ``punto_control`` del paso).

    Args:
        timeout_real_s: si se define, se compara con la duración real del paso y
            se emite un evento ``timeout_real`` (WARNING) si se excede. Con
            herramientas reales acá va el timeout del cliente HTTP / SDK.

    Returns:
        ``ResultadoReintento`` con ``estado`` OK, FALLBACK o FALLIDO.
    """
    contexto = dict(contexto or {})
    contexto.update({"paso": paso_id, "nombre_paso": nombre_paso, "agente": agente})
    reloj: RelojLogico | None = contexto.get("reloj")
    inicio_real = time.perf_counter()

    def _on_fallback(motivo: dict) -> dict | None:
        """Ejecuta el agente de respaldo (con reintentos propios)."""
        if accion_fallback is None:
            return None
        if reloj:
            reloj.avanzar(0.05)
        monitoreo.registrar_evento(
            {
                "evento": "fallback_activado",
                "paso": paso_id,
                "nombre_paso": nombre_paso,
                "agente": agente,
                "agente_fallback": nombre_fallback,
                "nivel": "WARNING",
                "codigo": "FALLBACK_ACTIVADO",
                "mensaje": (
                    f"'{agente}' agotó {motivo.get('intentos')} intentos ({motivo.get('codigo')}); "
                    f"se degrada a '{nombre_fallback}'"
                ),
                "motivo": motivo.get("codigo"),
                "intentos": motivo.get("intentos"),
                "t_logico_s": _tick(reloj),
            }
        )
        contexto_fb = dict(contexto)
        contexto_fb["agente"] = nombre_fallback
        resultado_fb = reintentar(
            accion_fallback,
            max_reintentos=max_reintentos_fallback,
            backoff_base=backoff_base,
            on_fallback=None,
            factor=factor,
            jitter=jitter,
            rng=rng,
            contexto=contexto_fb,
            escala_tiempo=escala_tiempo,
            dormir=dormir,
        )
        if not resultado_fb.ok:
            monitoreo.registrar_evento(
                {
                    "evento": "fallback_fallido",
                    "paso": paso_id,
                    "nombre_paso": nombre_paso,
                    "agente": nombre_fallback,
                    "nivel": "ERROR",
                    "mensaje": "el agente de respaldo tampoco pudo completar el paso",
                    "t_logico_s": _tick(reloj),
                }
            )
            return None
        salida: dict[str, Any] = dict(resultado_fb.resultado or {})
        salida["intentos_fallback"] = resultado_fb.intentos
        salida["intentos_fallback_total"] = resultado_fb.total_intentos
        return salida

    resultado = reintentar(
        accion,
        max_reintentos=max_reintentos,
        backoff_base=backoff_base,
        on_fallback=_on_fallback,
        factor=factor,
        jitter=jitter,
        rng=rng,
        contexto=contexto,
        escala_tiempo=escala_tiempo,
        dormir=dormir,
        solo_reintentables=solo_reintentables,
    )

    if timeout_real_s is not None and time.perf_counter() - inicio_real > timeout_real_s:
        resultado.alertas.append(
            f"el paso {nombre_paso} excedió el timeout real de {timeout_real_s}s"
        )
        monitoreo.registrar_evento(
            {
                "evento": "timeout_real",
                "paso": paso_id,
                "nombre_paso": nombre_paso,
                "agente": agente,
                "nivel": "ERROR",
                "mensaje": resultado.alertas[-1],
                "t_logico_s": _tick(reloj),
            }
        )

    return resultado
