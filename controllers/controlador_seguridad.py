"""
Seccion Seguridad (solo administrador): historial de accesos y respaldos.
"""

from database import respaldo
from helpers import permisos
from models import acceso


def obtener_historial_accesos(limite=1000):
    if not permisos.es_admin():
        return []
    return acceso.listar_historial(limite)


def obtener_estado_respaldos():
    """Datos para la tarjeta de respaldos."""
    respaldos = respaldo.listar_respaldos()
    return {
        "carpeta": respaldo.CARPETA_RESPALDOS,
        "cantidad": len(respaldos),
        "ultimo": respaldos[0][1] if respaldos else None,
        "proximo": respaldo.fecha_proximo_respaldo(),
        "dias": respaldo.DIAS_ENTRE_RESPALDOS,
        "maximo": respaldo.MAX_RESPALDOS,
        "respaldos": respaldos,
    }


def crear_respaldo_manual():
    """Devuelve (exito, mensaje)."""
    if not permisos.es_admin():
        return False, "Solo el administrador puede crear respaldos."
    try:
        ruta = respaldo.crear_respaldo()
    except Exception as error:
        return False, f"No se pudo crear el respaldo: {error}"
    return True, f"Respaldo creado: {ruta}"
