"""Agentes de automatización: cada agente envuelve una herramienta simulada.

Un agente es una unidad de trabajo con un objetivo único ("cobrar", "descontar
stock", "emitir guía", "avisar al cliente"). La clase base ``Agente`` resuelve
lo que en un agente real es la "capa de decisión":

    * sortea la latencia de la llamada y avanza el reloj lógico;
    * sortea si la herramienta falla, con la probabilidad de config;
    * dispara el **timeout simulado** si la latencia sorteada supera el umbral;
    * clasifica el fallo como reintentable (caída del servicio) o no (rechazo de
    negocio) y levanta ``ErrorAgente`` / ``ErrorTimeoutAgente``.

``ejecutar()`` es el método que cada agente concreto sobreescribe: ahí vive la
lógica de negocio "de verdad" (el resto es simulación). Con una API real, sólo
cambia el cuerpo de ``ejecutar()`` por la llamada HTTP; todo lo demás —reintentos,
backoff, fallback y monitoreo— no se toca (ver docs/ADAPTAR_A_PRODUCCION.md).

Uso:
    from agentes import construir_agentes
    agentes = construir_agentes(config, rng)
    salida = agentes["AgenteValidarPago"].simular(contexto)
"""

from __future__ import annotations

import random
import time
from typing import Callable

from manejo_errores import ErrorAgente, ErrorTimeoutAgente, RelojLogico

CODIGO_INDISPONIBLE = "INDISPONIBLE"
CODIGO_RECHAZO = "RECHAZO_NEGOCIO"
CODIGO_SIN_STOCK = "STOCK_INSUFICIENTE"
CODIGO_DOMICILIO = "DOMICILIO_INVALIDO"
CODIGO_SIN_CONTACTO = "CONTACTO_INDISPONIBLE"
CODIGO_SIN_RESERVA = "SIN_RESERVA_STOCK"

Accion = Callable[[int], dict]


class Agente:
    """Clase base de los agentes: lógica de decisión común a todas las herramientas.

    Attributes:
        nombre: identificador del agente (clave en ``config.json``).
        descripcion: qué hace, en una línea.
        herramienta_real: a qué se mapea en producción (API, cola, función).
        prob_fallo: probabilidad de que la herramienta falle en un intento.
        prob_rechazo: probabilidad de un rechazo de negocio (no reintentable).
        latencia_ms: rango de latencia simulada de la llamada.
        timeout_simulado_ms: umbral que dispara el timeout simulado.
    """

    etiqueta_error = "GEN"

    def __init__(
        self,
        nombre: str,
        *,
        descripcion: str = "",
        herramienta_real: str = "",
        prob_fallo: float = 0.1,
        prob_rechazo: float = 0.0,
        latencia_ms: tuple[int, int] = (100, 300),
        timeout_simulado_ms: int = 1000,
        rng: random.Random | None = None,
        escala_latencia: float = 1.0,
    ) -> None:
        self.nombre = nombre
        self.descripcion = descripcion
        self.herramienta_real = herramienta_real
        self.prob_fallo = float(prob_fallo)
        self.prob_rechazo = float(prob_rechazo)
        self.latencia_ms = (int(latencia_ms[0]), int(latencia_ms[1]))
        self.timeout_simulado_ms = int(timeout_simulado_ms)
        self.rng = rng if rng is not None else random.Random()
        self.escala_latencia = float(escala_latencia)
        self.llamadas = 0

    # ------------------------------------------------------------------ #
    # Método a sobreescribir por cada agente concreto
    # ------------------------------------------------------------------ #
    def ejecutar(self, contexto: dict) -> dict:
        """Ejecuta la lógica de negocio del agente y devuelve su salida."""
        raise NotImplementedError("Cada agente debe implementar ejecutar()")

    # ------------------------------------------------------------------ #
    # Capa de decisión (simulación de la herramienta real)
    # ------------------------------------------------------------------ #
    def simular(self, contexto: dict) -> dict:
        """Ejecuta un intento completo: latencia → falla/timeout → ``ejecutar()``.

        Args:
            contexto: contexto del pedido (ver ``config.json`` → ``tarea.contexto``).

        Returns:
            El dict que devuelve ``ejecutar()``, más ``latencia_sim_ms``.

        Raises:
            ErrorTimeoutAgente: la latencia sorteada superó el timeout.
            ErrorAgente: la herramienta simulada falló o rechazó la operación.
        """
        reloj: RelojLogico | None = contexto.get("reloj")
        latencia_ms = self._sortear_latencia()
        if reloj:
            reloj.avanzar(latencia_ms / 1000.0)
        self._dormir(latencia_ms)
        self.llamadas += 1

        if latencia_ms > self.timeout_simulado_ms:
            raise ErrorTimeoutAgente(
                f"TIMEOUT_{self.etiqueta_error}",
                f"la herramienta no respondió en {latencia_ms:.0f} ms "
                f"(timeout configurado: {self.timeout_simulado_ms} ms)",
                reintentable=True,
                herramienta=self.herramienta_real,
                latencia_sim_ms=latencia_ms,
            )

        modo = self._sortear_falla()
        if modo == "rechazo":
            raise self._rechazo(latencia_ms)
        if modo == "indisponible":
            raise ErrorAgente(
                f"{CODIGO_INDISPONIBLE}_{self.etiqueta_error}",
                "la herramienta respondió con error transitorio (503 / ECONNRESET simulado)",
                reintentable=True,
                herramienta=self.herramienta_real,
                latencia_sim_ms=latencia_ms,
            )

        salida = self.ejecutar(contexto)
        salida["latencia_sim_ms"] = latencia_ms
        salida["agente"] = self.nombre
        salida.setdefault("herramienta_real", self.herramienta_real)
        return salida

    def _sortear_latencia(self) -> float:
        """Sortea la latencia de la llamada en milisegundos."""
        bajo, alto = self.latencia_ms
        return round(self.rng.uniform(bajo, alto), 1)

    def _sortear_falla(self) -> str | None:
        """Decide si este intento falla por error de la herramienta o de negocio.

        Returns:
            ``"indisponible"``, ``"rechazo"`` o ``None``. El timeout no se sortea
            acá: surge de comparar la latencia contra ``timeout_simulado_ms``.
        """
        if self.prob_rechazo > 0 and self.rng.random() < self.prob_rechazo:
            return "rechazo"
        if self.prob_fallo > 0 and self.rng.random() < self.prob_fallo:
            return "indisponible"
        return None

    def _rechazo(self, latencia_ms: float) -> ErrorAgente:
        """Construye el error de rechazo de negocio (NO reintentable)."""
        return ErrorAgente(
            f"{CODIGO_RECHAZO}_{self.etiqueta_error}",
            "la operación fue rechazada por regla de negocio; reintentar no ayuda",
            reintentable=False,
            herramienta=self.herramienta_real,
            latencia_sim_ms=latencia_ms,
        )

    def _dormir(self, latencia_ms: float) -> None:
        """Duerme la latencia real comprimida por ``escala_latencia``."""
        if self.escala_latencia > 0:
            time.sleep(latencia_ms / 1000.0 * self.escala_latencia)

    def _serie(self, prefijo: str, longitud: int = 6) -> str:
        """Genera un identificador pseudoaleatorio reproducible (ej. AUTH-4821)."""
        return f"{prefijo}-{self.rng.randrange(10 ** (longitud - 1), 10 ** longitud)}"

    def __repr__(self) -> str:  # pragma: no cover - conveniencia de depuración
        return f"{type(self).__name__}(nombre={self.nombre!r}, prob_fallo={self.prob_fallo})"


class AgenteValidarPago(Agente):
    """Paso 1: confirma el cobro del pedido en la pasarela de pagos.

    Fallas simuladas: la pasarela cae (reintentable con backoff) o rechaza el
    cobro (no reintentable → el pedido se frena, no se toca el stock).
    Fallback: no hay, porque sin pago confirmado no se puede despachar.
    """

    etiqueta_error = "PAGO"

    def ejecutar(self, contexto: dict) -> dict:
        """Valida el pago y devuelve la autorización."""
        monto = contexto.get("monto", 0.0)
        if monto <= 0:
            raise ErrorAgente(
                CODIGO_RECHAZO,
                f"monto inválido ({monto}); el pago no puede confirmarse",
                reintentable=False,
                herramienta=self.herramienta_real,
            )
        contexto["pago_confirmado"] = True
        return {
            "accion": "confirmar_pago",
            "pedido_id": contexto.get("pedido_id"),
            "monto": monto,
            "moneda": contexto.get("moneda", "ARS"),
            "estado": "aprobado",
            "autorizacion": self._serie("AUTH", 8),
            "detalle": f"pago de {monto:,.0f} {contexto.get('moneda', 'ARS')} aprobado",
        }


class AgenteActualizarStock(Agente):
    """Paso 2: descuenta unidades en el ERP de depósito (servicio intermitente).

    Fallas simuladas: el ERP no responde (timeout) o devuelve 503. Es el paso
    con más riesgo: por eso tiene agente de respaldo.
    Fallback: ``AgenteFallbackStock`` (planilla manual + ticket humano).
    """

    etiqueta_error = "ERP"

    def ejecutar(self, contexto: dict) -> dict:
        """Descuenta el stock reservado para el pedido."""
        items = contexto.get("items", [])
        unidades = sum(int(item.get("cantidad", 0)) for item in items)
        stock = int(contexto.get("stock", 0))
        if unidades > stock:
            raise ErrorAgente(
                CODIGO_SIN_STOCK,
                f"stock insuficiente ({stock} disponibles, {unidades} pedidos); "
                "no es un problema transitorio",
                reintentable=False,
                herramienta=self.herramienta_real,
            )
        contexto["stock"] = stock - unidades
        contexto["stock_reservado"] = True
        return {
            "accion": "descontar_stock",
            "pedido_id": contexto.get("pedido_id"),
            "unidades": unidades,
            "stock_restante": contexto["stock"],
            "reserva_id": self._serie("RSV", 8),
            "detalle": f"{unidades} unidades descontadas, quedan {contexto['stock']} en depósito",
        }


class AgentePrepararEnvio(Agente):
    """Paso 3: genera la guía de envío y reserva cupo con el transportista.

    Fallas simuladas: el transportista no responde (reintentable) o el
    domicilio no es válido (no reintentable).
    Fallback: no hay, sin guía no se puede despachar; el orquestador frena.
    """

    etiqueta_error = "ENVIO"

    def ejecutar(self, contexto: dict) -> dict:
        """Emite la guía de envío y calcula el packaging."""
        if not contexto.get("stock_reservado"):
            raise ErrorAgente(
                CODIGO_SIN_RESERVA,
                "no hay stock reservado: el envío no puede armarse",
                reintentable=False,
                herramienta=self.herramienta_real,
            )
        if not contexto.get("domicilio_ok", True):
            raise ErrorAgente(
                f"{CODIGO_DOMICILIO}",
                "el domicilio del cliente no pudo validarse contra el servicio de envíos",
                reintentable=False,
                herramienta=self.herramienta_real,
            )
        items = contexto.get("items", [])
        peso_kg = round(sum(0.9 * int(i.get("cantidad", 1)) for i in items), 1)
        transportista = self.rng.choice(["EnvíaYa", "RápidoSur", "CargoExpress"])
        demora_h = self.rng.choice([24, 48, 72])
        contexto["envio_preparado"] = True
        return {
            "accion": "preparar_envio",
            "pedido_id": contexto.get("pedido_id"),
            "transportista": transportista,
            "guia": self._serie("GUIA", 10),
            "bultos": max(1, len(items) // 2),
            "peso_kg": peso_kg,
            "demora_h": demora_h,
            "detalle": f"guía emitida con {transportista} (demora estimada {demora_h} h)",
        }


class AgenteNotificar(Agente):
    """Paso 4: avisa al cliente por su canal (servicio de mensajería inestable).

    Fallas simuladas: el proveedor de mensajería cae o tarda (timeout). Como es
    el último paso, si falla no se pierde el pedido: el orquestador emite alerta
    para el contacto manual.
    Fallback: no hay agente; la mitigación es la alerta + reintento.
    """

    etiqueta_error = "NOTIF"

    def ejecutar(self, contexto: dict) -> dict:
        """Envía el aviso de confirmación y seguimiento al cliente."""
        canal = contexto.get("canal", "email")
        if not contexto.get("contacto_ok", True):
            raise ErrorAgente(
                CODIGO_SIN_CONTACTO,
                f"el cliente no tiene {canal} verificado; no se puede avisar",
                reintentable=False,
                herramienta=self.herramienta_real,
            )
        guia = contexto.get("guia", "pendiente")
        return {
            "accion": "notificar_cliente",
            "pedido_id": contexto.get("pedido_id"),
            "canal": canal,
            "destinatario": contexto.get("cliente"),
            "mensaje_id": self._serie("MSG", 8),
            "guia": guia,
            "detalle": f"aviso de envío enviado por {canal} (guía {guia})",
        }


class AgenteFallbackStock(Agente):
    """Respaldo del paso 2: control de stock manual + ticket de revisión humana.

    Herramienta real equivalente: escribir en la planilla de control y abrir un
    ticket (Jira/Zendesk). Es la degradación operativa: el pedido no se frena,
    pero queda una tarea humana y trazable.
    """

    etiqueta_error = "STOCK_MANUAL"

    def ejecutar(self, contexto: dict) -> dict:
        """Descuenta el stock en la planilla manual y abre el ticket."""
        items = contexto.get("items", [])
        unidades = sum(int(item.get("cantidad", 0)) for item in items)
        stock = int(contexto.get("stock", 0))
        contexto["stock"] = max(0, stock - unidades)
        contexto["stock_reservado"] = True
        contexto["revision_humana"] = True
        ticket = self._serie("TK", 6)
        return {
            "accion": "stock_manual",
            "pedido_id": contexto.get("pedido_id"),
            "unidades": unidades,
            "stock_restante": contexto["stock"],
            "ticket": ticket,
            "revision_humana": True,
            "detalle": (
                f"stock descontado en planilla manual y ticket {ticket} abierto "
                "para revisión humana antes del despacho"
            ),
        }


REGISTRO_AGENTES: dict[str, type[Agente]] = {
    "AgenteValidarPago": AgenteValidarPago,
    "AgenteActualizarStock": AgenteActualizarStock,
    "AgentePrepararEnvio": AgentePrepararEnvio,
    "AgenteNotificar": AgenteNotificar,
    "AgenteFallbackStock": AgenteFallbackStock,
}


def construir_agentes(
    config: dict,
    rng: random.Random | None = None,
) -> dict[str, Agente]:
    """Instancia todos los agentes declarados en ``config.json``.

    Args:
        config: diccionario de configuración ya cargado.
        rng: generador con semilla fija (reproducibilidad).

    Returns:
        Mapa ``nombre -> instancia de Agente``.
    """
    generador = rng if rng is not None else random.Random()
    escala = float(config.get("simulacion", {}).get("escala_latencia", 1.0))
    agentes: dict[str, Agente] = {}
    for nombre, cfg in config.get("agentes", {}).items():
        clase = REGISTRO_AGENTES.get(cfg.get("clase", nombre))
        if clase is None:
            raise KeyError(f"agente desconocido en config.json: {nombre}")
        agentes[nombre] = clase(
            nombre,
            descripcion=cfg.get("descripcion", ""),
            herramienta_real=cfg.get("herramienta_real", ""),
            prob_fallo=cfg.get("prob_fallo", 0.0),
            prob_rechazo=cfg.get("prob_rechazo", 0.0),
            latencia_ms=tuple(cfg.get("latencia_ms", (100, 300))),  # type: ignore[arg-type]
            timeout_simulado_ms=cfg.get("timeout_simulado_ms", 1000),
            rng=generador,
            escala_latencia=escala,
        )
    return agentes


def ejecutar_agente(agente: Agente, contexto: dict) -> dict:
    """Ejecuta un agente sobre el contexto y normaliza el resultado o el error.

    Es el adaptador que usa el orquestador para exponer cada agente como una
    ``accion(numero_intento) -> dict`` para :mod:`manejo_errores`.

    Args:
        agente: agente a ejecutar.
        contexto: contexto del pedido.

    Returns:
        ``{"ok": True, "salida": {...}}`` o ``{"ok": False, "error": ErrorAgente}``.
    """
    try:
        salida = agente.simular(contexto)
    except ErrorAgente as error:
        return {"ok": False, "error": error}
    return {"ok": True, "salida": salida}


__all__ = [
    "Accion",
    "Agente",
    "AgenteValidarPago",
    "AgenteActualizarStock",
    "AgentePrepararEnvio",
    "AgenteNotificar",
    "AgenteFallbackStock",
    "REGISTRO_AGENTES",
    "construir_agentes",
    "ejecutar_agente",
]
