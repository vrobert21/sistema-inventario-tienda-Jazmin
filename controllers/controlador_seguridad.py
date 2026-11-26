"""
Seccion Seguridad (solo administrador): historial de accesos y respaldos.
"""

import traceback

from database import respaldo
from helpers import permisos
from models import acceso


def obtener_historial_accesos(limite=1000):
    if not permisos.es_admin():
        return []
    return acceso.listar_historial(limite)


def exportar_historial_accesos(ruta, limite=1000):
    """PDF con el historial de accesos completo. Devuelve (exito, mensaje)."""
    if not permisos.es_admin():
        return False, "Solo el administrador puede exportar el historial."

    try:
        from reportes.pdf_historial import generar_pdf_historial
    except ModuleNotFoundError as error:
        if not (error.name or "").startswith("reportlab"):
            raise
        return False, ("Falta la biblioteca ReportLab para crear PDF. "
                       "Instálala con:  uv pip install --python .venv reportlab")

    try:
        generar_pdf_historial(acceso.listar_historial(limite), ruta)
        return True, f"Historial guardado en {ruta}"
    except PermissionError:
        return False, ("No se pudo guardar el archivo. Si ese PDF está abierto en otro "
                       "programa, ciérralo o elige otro nombre.")
    except Exception as error:
        traceback.print_exc()
        return False, f"No se pudo generar el PDF ({error})."


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
