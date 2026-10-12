"""
Respaldos de la base de datos.

Se guardan en la carpeta "respaldos" junto a tienda_jazmin.db (o junto
al .exe en la version compilada). Cada respaldo es una copia completa
de la base, hecha con la API de backup de SQLite: es segura aunque el
programa tenga la base abierta.

- respaldo_automatico_si_toca(): crea un respaldo si el ultimo tiene
  DIAS_ENTRE_RESPALDOS dias o mas. Se llama al arrancar y cada hora
  mientras el programa este abierto (ver ui/app.py).
- crear_respaldo(): respaldo inmediato (boton "Crear respaldo ahora").

Solo se conservan los MAX_RESPALDOS mas recientes.

Para restaurar un respaldo: cerrar el programa, copiar el archivo
deseado sobre tienda_jazmin.db y volver a abrir.
"""

import os
import sqlite3
from datetime import datetime, timedelta

from database.conexion import RUTA_BASE_DATOS, obtener_conexion

CARPETA_RESPALDOS = os.path.join(os.path.dirname(RUTA_BASE_DATOS), "respaldos")
DIAS_ENTRE_RESPALDOS = 2
MAX_RESPALDOS = 15

_PREFIJO = "tienda_jazmin_"
_EXTENSION = ".db"
_FORMATO_NOMBRE = "%Y-%m-%d_%H%M%S"


def _fecha_de(nombre_archivo):
    """Lee la fecha del nombre 'tienda_jazmin_2026-10-11_143000.db', o None."""
    if not (nombre_archivo.startswith(_PREFIJO) and nombre_archivo.endswith(_EXTENSION)):
        return None
    texto = nombre_archivo[len(_PREFIJO):-len(_EXTENSION)]
    try:
        return datetime.strptime(texto, _FORMATO_NOMBRE)
    except ValueError:
        return None


def listar_respaldos():
    """Lista de (ruta, fecha, tamano_bytes), del mas reciente al mas antiguo."""
    if not os.path.isdir(CARPETA_RESPALDOS):
        return []

    respaldos = []
    for nombre in os.listdir(CARPETA_RESPALDOS):
        fecha = _fecha_de(nombre)
        if fecha is None:
            continue
        ruta = os.path.join(CARPETA_RESPALDOS, nombre)
        respaldos.append((ruta, fecha, os.path.getsize(ruta)))

    respaldos.sort(key=lambda r: r[1], reverse=True)
    return respaldos


def fecha_ultimo_respaldo():
    respaldos = listar_respaldos()
    return respaldos[0][1] if respaldos else None


def fecha_proximo_respaldo():
    """Cuando toca el siguiente respaldo automatico (None = en cuanto se revise)."""
    ultimo = fecha_ultimo_respaldo()
    return ultimo + timedelta(days=DIAS_ENTRE_RESPALDOS) if ultimo else None


def crear_respaldo():
    """Copia la base a la carpeta de respaldos. Devuelve la ruta creada."""
    os.makedirs(CARPETA_RESPALDOS, exist_ok=True)

    nombre = _PREFIJO + datetime.now().strftime(_FORMATO_NOMBRE) + _EXTENSION
    ruta = os.path.join(CARPETA_RESPALDOS, nombre)
    temporal = ruta + ".tmp"

    origen = obtener_conexion()
    destino = sqlite3.connect(temporal)
    try:
        origen.backup(destino)
    finally:
        destino.close()
        origen.close()

    # Se escribe primero en .tmp para no dejar un respaldo a medias
    # si el programa se cierra durante la copia.
    os.replace(temporal, ruta)

    _borrar_antiguos()
    return ruta


def respaldo_automatico_si_toca():
    """Crea un respaldo si nunca se hizo o si el ultimo ya tiene 2 dias. Devuelve la ruta o None."""
    ultimo = fecha_ultimo_respaldo()
    if ultimo is not None and datetime.now() - ultimo < timedelta(days=DIAS_ENTRE_RESPALDOS):
        return None
    return crear_respaldo()


def _borrar_antiguos():
    for ruta, _fecha, _tamano in listar_respaldos()[MAX_RESPALDOS:]:
        try:
            os.remove(ruta)
        except OSError:
            pass
