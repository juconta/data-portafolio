#!/usr/bin/env python3
"""Escaner estatico de seguridad para proyectos Python / web.

Analiza una carpeta y busca los errores de seguridad mas comunes de una
pyme: secretos escritos en el codigo, archivos sensibles versionados, modo
debug prendido, CORS abierto a cualquier origen, endpoints de login sin
limite de intentos, eval/exec/pickle, contrasenas por defecto, inyeccion SQL,
cookies sin proteccion y ausencia de headers de seguridad.

Es un analisis 100% estatico: lee los archivos de texto, NO importa ni
ejecuta el codigo auditado y NO hace peticiones de red. Por eso sirve para
revisar el codigo de un cliente sin tocar su servidor.

Uso:
    python escaner.py app_vulnerable --reporte hallazgos/INFORME_AUDITORIA.md
    python escaner.py app_segura --reporte hallazgos/INFORME_SEGURA.md
    python escaner.py app_segura --min-severidad ALTA

La configuracion vive en rules.json (patrones, severidad, recomendacion).
"""

from __future__ import annotations

import argparse
import bisect
import dataclasses
import datetime
import fnmatch
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ARCHIVO_REGLAS_POR_DEFECTO = RAIZ / "rules.json"
MARCA_ANEXO = "<!-- ANEXO-MANUAL -->"

ORDEN_SEVERIDAD = {"CRITICA": 0, "ALTA": 1, "MEDIA": 2, "BAJA": 3}
NIVELES = ("CRITICA", "ALTA", "MEDIA", "BAJA")

VALOR_POR_DEFECTO: dict = {
    "version": "1.0",
    "ignorar_comentarios": True,
    "maximo_por_archivo": 3,
    "extensiones": [".py"],
    "nombres_adicionales": [],
    "carpetas_ignoradas": [".git", "__pycache__", ".venv", "node_modules"],
    "ignorados": [],
    "comentarios_solo_en": [".py"],
    "mapa_prioridad": {
        "CRITICA": "P0 - Inmediata",
        "ALTA": "P1 - Alta",
        "MEDIA": "P2 - Media",
        "BAJA": "P3 - Planeada",
    },
    "archivos_sensibles": [],
    "reglas": [],
}


@dataclasses.dataclass
class Hallazgo:
    """Un problema detectado: identificador, ubicacion y como corregirlo."""

    id: str
    nombre: str
    severidad: str
    categoria: str
    archivo: str
    linea: int
    evidencia: str
    descripcion: str
    recomendacion: str
    prioridad: str
    tipo: str
    ocurrencias: int = 1


# --------------------------------------------------------------------------
# Carga de configuracion
# --------------------------------------------------------------------------
def cargar_reglas(ruta: Path | None = None) -> dict:
    """Lee rules.json y completa los valores que no esten definidos."""
    ruta = ruta or ARCHIVO_REGLAS_POR_DEFECTO
    with ruta.open(encoding="utf-8") as archivo:
        datos = json.load(archivo)
    config = dict(VALOR_POR_DEFECTO)
    config.update(datos)
    return config


def prioridad_de(severidad: str, config: dict) -> str:
    """Devuelve la etiqueta de prioridad (P0, P1, ...) de una severidad."""
    mapa = config.get("mapa_prioridad", {})
    return mapa.get(severidad, "P3 - Planeada")


# --------------------------------------------------------------------------
# Recorrido de archivos
# --------------------------------------------------------------------------
def ruta_relativa(ruta: Path, base: Path) -> str:
    """Devuelve la ruta con '/', relativa a la carpeta auditada."""
    try:
        return ruta.resolve().relative_to(base.resolve()).as_posix()
    except ValueError:
        return ruta.name


def iterar_archivos(raiz: Path, config: dict) -> list[Path]:
    """Lista los archivos de texto a analizar, salteando los irrelevantes."""
    extensiones = {e.lower() for e in config["extensiones"]}
    nombres = {n.lower() for n in config["nombres_adicionales"]}
    carpetas_ignoradas = set(config["carpetas_ignoradas"])
    ignorados = set(config["ignorados"])

    archivos: list[Path] = []
    for ruta in sorted(raiz.rglob("*")):
        if not ruta.is_file():
            continue
        if any(parte in carpetas_ignoradas for parte in ruta.parts):
            continue
        if ruta.name in ignorados:
            continue
        if ruta.suffix.lower() in extensiones or ruta.name.lower() in nombres:
            archivos.append(ruta)
    return archivos


def leer_texto(ruta: Path) -> str | None:
    """Lee un archivo como texto UTF-8; None si es binario o no se puede."""
    try:
        return ruta.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def inicios_de_linea(texto: str) -> list[int]:
    """Posiciones (offset) donde arranca cada linea, para mapear matches."""
    inicios = [0]
    for indice, caracter in enumerate(texto):
        if caracter == "\n":
            inicios.append(indice + 1)
    return inicios


def linea_de(posicion: int, inicios: list[int]) -> int:
    """Traduce una posicion del texto a numero de linea (base 1)."""
    return bisect.bisect_right(inicios, posicion)


def linea_actual(texto: str, inicios: list[int]) -> dict:
    """Mapea numero de linea -> contenido de esa linea."""
    lineas = texto.splitlines()
    return {numero + 1: lineas[numero] for numero in range(len(lineas))}


def es_comentario(texto: str, posicion: int) -> bool:
    """True si el match arranca despues de un # en su misma linea.

    Es una aproximacion pensada para Python y archivos de configuracion: un
    comentario arranca con #, asi que si el # aparece antes del match en la
    misma linea, lo que hay desde ahi es texto comentado y no codigo. Asi los
    textos explicativos que el equipo deja al lado del codigo no se reportan
    como si fueran un problema.
    """
    inicio_linea = texto.rfind("\n", 0, posicion) + 1
    fin_linea = texto.find("\n", posicion)
    if fin_linea == -1:
        fin_linea = len(texto)
    columna_hash = texto.find("#", inicio_linea, fin_linea)
    return columna_hash != -1 and columna_hash < posicion - inicio_linea


def tiene_comentarios(ruta: Path, config: dict) -> bool:
    """True si el formato del archivo usa # para comentarios."""
    if ruta.name.lower().startswith(".env"):
        return True
    return ruta.suffix.lower() in set(config["comentarios_solo_en"])


def limpiar_evidencia(linea: str, limite: int = 130) -> str:
    """Compacta una linea de codigo para usarla como evidencia legible."""
    texto = " ".join(linea.strip().split())
    if len(texto) > limite:
        texto = texto[: limite - 1] + "…"
    return texto.replace("|", "\\|")


def evidencia_de(coincidencia: re.Match, texto: str, inicios: list[int], lineas: dict) -> tuple[int, str]:
    """Devuelve (linea, evidencia) del match.

    Si el patron abarca varias lineas (por ejemplo una consulta SQL armada
    con una f-string en la linea siguiente) se muestra el texto del match
    recorrido en una sola linea, porque ahi esta la evidencia real.
    """
    inicio = coincidencia.start()
    numero = linea_de(inicio, inicios)
    if "\n" in coincidencia.group(0):
        return numero, limpiar_evidencia(coincidencia.group(0))
    return numero, limpiar_evidencia(lineas.get(numero, ""))


# --------------------------------------------------------------------------
# Analisis
# --------------------------------------------------------------------------
def analizar_carpeta(raiz: Path, config: dict, min_severidad: str) -> list[Hallazgo]:
    """Recorre la carpeta y devuelve los hallazgos ordenados por severidad."""
    hallazgos: list[Hallazgo] = []
    vistos: set[tuple] = set()
    maximo = int(config.get("maximo_por_archivo", 3))
    ignorar_comentarios = config.get("ignorar_comentarios", True)
    umbral = ORDEN_SEVERIDAD.get(min_severidad, 3)

    def agregar(hallazgo: Hallazgo) -> None:
        if ORDEN_SEVERIDAD.get(hallazgo.severidad, 3) > umbral:
            return
        clave = (hallazgo.id, hallazgo.archivo, hallazgo.linea)
        if clave in vistos:
            return
        vistos.add(clave)
        hallazgos.append(hallazgo)

    for ruta in iterar_archivos(raiz, config):
        relativo = ruta_relativa(ruta, raiz)

        for patron in config["archivos_sensibles"]:
            if fnmatch.fnmatch(ruta.name.lower(), patron["patron"].lower()):
                agregar(
                    Hallazgo(
                        id="ARCH-SENS",
                        nombre=patron["nombre"],
                        severidad=patron["severidad"],
                        categoria=patron.get("categoria", "Secretos"),
                        archivo=relativo,
                        linea=0,
                        evidencia=f"archivo presente: {relativo}",
                        descripcion=patron["descripcion"],
                        recomendacion=patron["recomendacion"],
                        prioridad=prioridad_de(patron["severidad"], config),
                        tipo="archivo",
                    )
                )
                break

        texto = leer_texto(ruta)
        if texto is None:
            continue

        inicios = inicios_de_linea(texto)
        lineas = linea_actual(texto, inicios)
        comentarios = ignorar_comentarios and tiene_comentarios(ruta, config)
        mostrados_por_regla: dict[str, int] = {}
        ocurrencias_por_regla: dict[str, int] = {}

        for regla in config["reglas"]:
            tipo = regla.get("tipo", "regex")
            solo_archivos = regla.get("archivos")
            if solo_archivos and not any(fnmatch.fnmatch(relativo, p) for p in solo_archivos):
                continue

            if tipo == "ausencia_de_patron":
                if re.search(regla["detecta"], texto) and not re.search(regla["requiere"], texto):
                    coincidencia = re.search(regla["detecta"], texto)
                    numero = linea_de(coincidencia.start(), inicios)
                    agregar(
                        Hallazgo(
                            id=regla["id"],
                            nombre=regla["nombre"],
                            severidad=regla["severidad"],
                            categoria=regla.get("categoria", "General"),
                            archivo=relativo,
                            linea=numero,
                            evidencia=limpiar_evidencia(lineas.get(numero, "")),
                            descripcion=regla["descripcion"],
                            recomendacion=regla["recomendacion"],
                            prioridad=prioridad_de(regla["severidad"], config),
                            tipo=tipo,
                        )
                    )
                continue

            patron = regla["patron"]
            for coincidencia in re.finditer(patron, texto, re.MULTILINE):
                if comentarios and es_comentario(texto, coincidencia.start()):
                    continue
                ocurrencias_por_regla[regla["id"]] = (
                    ocurrencias_por_regla.get(regla["id"], 0) + 1
                )
                if mostrados_por_regla.get(regla["id"], 0) >= maximo:
                    continue
                mostrados_por_regla[regla["id"]] = mostrados_por_regla.get(regla["id"], 0) + 1
                numero, evidencia = evidencia_de(coincidencia, texto, inicios, lineas)
                agregar(
                    Hallazgo(
                        id=regla["id"],
                        nombre=regla["nombre"],
                        severidad=regla["severidad"],
                        categoria=regla.get("categoria", "General"),
                        archivo=relativo,
                        linea=numero,
                        evidencia=evidencia,
                        descripcion=regla["descripcion"],
                        recomendacion=regla["recomendacion"],
                        prioridad=prioridad_de(regla["severidad"], config),
                        tipo=tipo,
                        ocurrencias=ocurrencias_por_regla[regla["id"]],
                    )
                )

    hallazgos.sort(
        key=lambda h: (ORDEN_SEVERIDAD.get(h.severidad, 3), h.archivo, h.linea, h.id)
    )
    return hallazgos


def contar_por_severidad(hallazgos: list[Hallazgo]) -> dict[str, int]:
    """Devuelve un diccionario severidad -> cantidad de hallazgos."""
    conteo = {nivel: 0 for nivel in NIVELES}
    for hallazgo in hallazgos:
        conteo[hallazgo.severidad] = conteo.get(hallazgo.severidad, 0) + 1
    return conteo


def veredicto(conteo: dict[str, int]) -> tuple[str, str]:
    """Resume el resultado en una frase de opinion para una pyme."""
    if conteo.get("CRITICA", 0):
        return (
            "NO APTO PARA PRODUCCION",
            "Hay problemas criticos que permiten alcanzar robo de datos o ejecutar codigo "
            "en el servidor. Hay que corregirlos antes de publicar la aplicacion.",
        )
    if conteo.get("ALTA", 0):
        return (
            "REVISAR ANTES DE PUBLICAR",
            "No hay problemas criticos, pero si riesgos altos que conviene corregir antes de poner la app en manos de los usuarios.",
        )
    if conteo.get("MEDIA", 0):
        return (
            "ACEPTABLE CON MEJORAS PENDIENTES",
            "No se detectan riesgos altos ni criticos. Quedan mejoras de buena practica para proche s>prints.",
        )
    return ("SIN RIESGOS DETECTADOS", "No se detectaron los patrones de este catalogo de reglas.")


# --------------------------------------------------------------------------
# Informe en Markdown
# --------------------------------------------------------------------------
def resumen_ejecutivo(hallazgos: list[Hallazgo], objetivo: str) -> str:
    """Redacta el resumen para un lector no tecnico (dueno de la pyme)."""
    conteo = contar_por_severidad(hallazgos)
    titulo, mensaje = veredicto(conteo)
    criticas = [h for h in hallazgos if h.severidad == "CRITICA"]
    altas = [h for h in hallazgos if h.severidad == "ALTA"]

    parrafos = [
        f"Este informe es el resultado de pasar el escaner estatico sobre `{objetivo}`. "
        "El escaner lee el codigo como texto y busca los errores de seguridad mas "
        "comunes: claves escondidas en el codigo, archivos de configuracion que no "
        "deberian subirse, funciones que ejecutan codigo recibido por Internet, "
        "contrasenas de fabrica y falta de controles basicos en el login.",
        "",
        f"**Resultado: {titulo}** - {mensaje}",
        "",
        f"Se detectaron **{len(hallazgos)} problemas** en total: "
        f"**{conteo.get('CRITICA', 0)} criticos**, {conteo.get('ALTA', 0)} altos, "
        f"{conteo.get('MEDIA', 0)} medios y {conteo.get('BAJA', 0)} bajos.",
    ]

    if criticas:
        temas = ", ".join(sorted({h.nombre.lower() for h in criticas}))
        parrafos += [
            "",
            "### Que significa esto para el negocio",
            "",
            f"Los {conteo.get('CRITICA', 0)} problemas criticos incluyen: {temas}.",
            "En la practica, esto significa que una persona no autorizada podria "
            "entrar al panel, leer datos de clientes o ejecutar acciones usando "
            "informacion que ya esta publicada en el propio repositorio.",
        ]
    if altas:
        temas_altos = ", ".join(sorted({h.nombre.lower() for h in altas})[:4])
        parrafos += [
            "",
            f"Entre los riesgos altos mas relevantes estan: {temas_altos}.",
        ]
    return "\n".join(parrafos)


def generar_informe(
    hallazgos: list[Hallazgo],
    objetivo: str,
    archivos: list[Path],
    config: dict,
    ruta_reporte: Path,
    reglas_cargadas: Path,
) -> str:
    """Arma el informe Markdown completo y lo escribe en disco."""
    conteo = contar_por_severidad(hallazgos)
    titulo, _ = veredicto(conteo)
    fecha = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    lineas = [
        f"# Informe de auditoria de seguridad - {objetivo}",
        "",
        "| Dato | Valor |",
        "|---|---|",
        f"| Fecha | {fecha} |",
        f"| Carpeta analizada | `{objetivo}` |",
        f"| Archivos de codigo revisados | {len(archivos)} |",
        f"| Reglas aplicadas | {len(config['reglas'])} patrones + "
        f"{len(config['archivos_sensibles'])} chequeos de archivos |",
        f"| Reglas desde | `{ruta_relativa(reglas_cargadas, RAIZ)}` |",
        f"| Total de hallazgos | {len(hallazgos)} |",
        f"| Opinion | **{titulo}** |",
        "",
        "> Analisis estatico: no se ejecuto el codigo auditado ni se realizo ninguna "
        "prueba de ataque contra un sistema. Todo se resolvio leyendo los archivos de texto.",
        "",
        "## 1. Resumen ejecutivo",
        "",
        resumen_ejecutivo(hallazgos, objetivo),
        "",
        "## 2. Conteo por severidad",
        "",
        "| Severidad | Cantidad | Prioridad | Significado |",
        "|---|---|---|---|",
    ]
    significados = {
        "CRITICA": "Se puede llegar a datos o control del servidor. Corregir ya.",
        "ALTA": "Facilita ataques comunes (fuerza bruta, robo de clave). Corregir esta semana.",
        "MEDIA": "Buenas practicas que reducen el riesgo. Corregir en el proximo sprint.",
        "BAJA": "Higiene de codigo. Anotado para limpiar cuando se pueda.",
    }
    for nivel in NIVELES:
        lineas.append(
            f"| {nivel} | {conteo.get(nivel, 0)} | "
            f"{prioridad_de(nivel, config)} | {significados[nivel]} |"
        )

    lineas += [
        "",
        "## 3. Hallazgos detallados",
        "",
        "| ID | Severidad | Prioridad | Hallazgo | Ubicacion | Evidencia |",
        "|---|---|---|---|---|---|",
    ]
    for hallazgo in hallazgos:
        ubicacion = (
            f"`{hallazgo.archivo}:{hallazgo.linea}`"
            if hallazgo.linea
            else f"`{hallazgo.archivo}`"
        )
        lineas.append(
            f"| {hallazgo.id} | {hallazgo.severidad} | {hallazgo.prioridad} | "
            f"{hallazgo.nombre} | {ubicacion} | `{hallazgo.evidencia}` |"
        )

    lineas += ["", "## 4. Que hacer y en que orden", ""]
    por_id: dict[str, list[Hallazgo]] = {}
    for hallazgo in hallazgos:
        por_id.setdefault(hallazgo.id, []).append(hallazgo)
    orden = sorted(por_id.values(), key=lambda grupo: ORDEN_SEVERIDAD.get(grupo[0].severidad, 3))
    for numero, grupo in enumerate(orden, start=1):
        primero = grupo[0]
        archivos_afectados = sorted({h.archivo for h in grupo})
        detalle_extra = (
            f" ({len(grupo)} ubicaciones)" if len(grupo) > 1 else ""
        )
        lineas.append(
            f"{numero}. **[{primero.id}] {primero.nombre}** "
            f"- {primero.severidad} / {primero.prioridad}{detalle_extra}.  "
            f"Archivos: {', '.join('`' + a + '`' for a in archivos_afectados)}."
        )
        lineas.append(f"   Como se corrige: {primero.recomendacion}")
    lineas += [
        "",
        "## 5. Detalle tecnico por hallazgo",
        "",
    ]
    for numero, grupo in enumerate(orden, start=1):
        primero = grupo[0]
        lineas += [
            f"### {numero}. {primero.id} - {primero.nombre}",
            "",
            f"- **Severidad:** {primero.severidad} ({primero.prioridad})",
            f"- **Categoria:** {primero.categoria}",
            f"- **Ocurrencias:** {len(grupo)} ubicacion(es) en {len(archivos_afectados)} archivo(s)",
            f"- **Por que importa:** {primero.descripcion}",
            f"- **Como se corrige:** {primero.recomendacion}",
            "",
            "| Archivo | Linea | Evidencia |",
            "|---|---|---|",
        ]
        for hallazgo in grupo:
            lineas.append(
                f"| `{hallazgo.archivo}` | {hallazgo.linea or '-'} | "
                f"`{hallazgo.evidencia}` |"
            )
        lineas.append("")

    lineas += [
        "## 6. Alcance y limites del escaneo",
        "",
        "- Analisis estatico sobre archivos de texto: no se ejecuta la aplicacion.",
        "- No se prueban exploits ni se hacen peticiones a servidores externos.",
        "- Los patrones son heuristicos: puede haber falsos positivos y, sobre todo, "
        "falsos negativos (codigo inseguro escrito de una forma no contemplada).",
        "- Este informe no reemplaza una auditoria humana ni un pentest.",
        "",
        "---",
        "",
        f"Generado por `escaner.py` el {fecha} usando las reglas de `rules.json`.",
        "",
    ]
    texto = "\n".join(lineas) + "\n"

    if ruta_reporte.exists():
        previo = ruta_reporte.read_text(encoding="utf-8")
        if MARCA_ANEXO in previo:
            texto += "\n" + previo[previo.index(MARCA_ANEXO) :]
    ruta_reporte.parent.mkdir(parents=True, exist_ok=True)
    ruta_reporte.write_text(texto, encoding="utf-8")
    return texto


# --------------------------------------------------------------------------
# Salida por consola
# --------------------------------------------------------------------------
def imprimir_consola(
    hallazgos: list[Hallazgo], objetivo: str, config: dict, ruta_reporte: Path | None
) -> None:
    """Muestra el resultado en formato texto plano (sirve para el reporte de consola)."""
    conteo = contar_por_severidad(hallazgos)
    titulo, mensaje = veredicto(conteo)
    ancho = 80
    print("=" * ancho)
    print(" ESCANER ESTATICO DE SEGURIDAD - Auditoria basica".center(ancho))
    print("=" * ancho)
    print(f" Fecha           : {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f" Carpeta         : {objetivo}")
    print(f" Reglas          : {len(config['reglas'])} patrones + "
          f"{len(config['archivos_sensibles'])} chequeos de archivos")
    print("-" * ancho)

    if not hallazgos:
        print(" Hallazgos       : ninguno")
    for hallazgo in hallazgos:
        ubicacion = f"{hallazgo.archivo}:{hallazgo.linea}" if hallazgo.linea else hallazgo.archivo
        print(f" [{hallazgo.severidad:^7}] {hallazgo.id:<9} {ubicacion}")
        print(f"             {hallazgo.nombre}")
        print(f"             {hallazgo.evidencia}")
        print(f"             Prioridad: {hallazgo.prioridad}")
        print()

    print("-" * ancho)
    print(" RESUMEN")
    print("-" * ancho)
    for nivel in NIVELES:
        print(f" {nivel:<8}: {conteo.get(nivel, 0)}")
    print(f" {'TOTAL':<8}: {len(hallazgos)}")
    print()
    print(f" Opinion         : {titulo}")
    print(f"                  {mensaje}")
    if ruta_reporte:
        print(f" Reporte         : {ruta_reporte}")
    print("=" * ancho)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def parsear_argumentos() -> argparse.Namespace:
    """Define y lee los argumentos de linea de comandos."""
    analizador = argparse.ArgumentParser(
        description="Escaner estatico de seguridad para apps Python/web.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    analizador.add_argument("objetivo", help="carpeta a auditar")
    analizador.add_argument(
        "--reporte", type=Path, default=None, help="ruta del informe Markdown a generar"
    )
    analizador.add_argument(
        "--reglas", type=Path, default=None, help="archivo de reglas (por defecto rules.json)"
    )
    analizador.add_argument(
        "--min-severidad", choices=NIVELES, default="BAJA", help="nivel minimo a reportar"
    )
    analizador.add_argument(
        "--analizar-comentarios",
        action="store_true",
        help="reportar tambien patrones que aparecen comentados en el codigo",
    )
    return analizador.parse_args()


def main() -> int:
    """Punto de entrada: audita la carpeta pedida e imprime el resumen."""
    argumentos = parsear_argumentos()
    objetivo = Path(argumentos.objetivo)
    if not objetivo.is_dir():
        print(f"ERROR: la carpeta {objetivo} no existe.")
        return 2

    config = cargar_reglas(argumentos.reglas)
    if argumentos.analizar_comentarios:
        config["ignorar_comentarios"] = False

    hallazgos = analizar_carpeta(objetivo, config, argumentos.min_severidad)
    ruta_reporte = argumentos.reporte
    if ruta_reporte is not None and not ruta_reporte.is_absolute():
        ruta_reporte = Path.cwd() / ruta_reporte
    if ruta_reporte is not None:
        generar_informe(
            hallazgos,
            objetivo.name,
            iterar_archivos(objetivo, config),
            config,
            ruta_reporte,
            argumentos.reglas or ARCHIVO_REGLAS_POR_DEFECTO,
        )

    imprimir_consola(hallazgos, objetivo.name, config, ruta_reporte)
    return 1 if contar_por_severidad(hallazgos).get("CRITICA", 0) else 0


if __name__ == "__main__":
    sys.exit(main())
