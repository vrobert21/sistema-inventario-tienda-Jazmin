"""
Historial de accesos (bitacora) en PDF.

Usa las mismas piezas de diseno que el resto de los reportes
(reportes/pdf.py): encabezado, pie con numeracion, tablas y colores.
Pensado para la pantalla Seguridad, que es la unica que muestra este
historial (solo administrador).
"""

from datetime import datetime
from functools import partial

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Spacer

from reportes.formato import ETIQUETA_EVENTO, fecha_hora
from reportes.pdf import ANCHO_UTIL, MARGEN_X, _CanvasNumerado, _estilos, _p, _tabla

_NOMBRE_ROL = {"admin": "Administrador", "vendedor": "Ventas"}


def generar_pdf_historial(filas, ruta):
    """
    filas: lo mismo que devuelve models.acceso.listar_historial (fecha,
    usuario, evento, detalle, nombre, rol), mas recientes primero.
    """
    e = _estilos()
    ahora = datetime.now()
    meta = {
        "titulo_reporte": "Historial de accesos",
        "periodo": f"{len(filas)} eventos",
        "pie": f"Generado el {ahora.strftime('%d/%m/%Y')} a las {ahora.strftime('%H:%M')}",
    }
    doc = SimpleDocTemplate(
        ruta, pagesize=A4, leftMargin=MARGEN_X, rightMargin=MARGEN_X,
        topMargin=2.6 * cm, bottomMargin=2.0 * cm,
        title="Historial de accesos", author="Tienda Jazmín",
    )

    h = [_p("Historial de accesos", e["titulo"]),
         _p(f"{len(filas)} eventos más recientes primero.", e["subtitulo"]),
         Spacer(1, 10)]

    if filas:
        datos = []
        for f in filas:
            cuenta = f"{f['nombre']} ({_NOMBRE_ROL.get(f['rol'], f['rol'])})" if f["nombre"] else "No existe"
            evento = ETIQUETA_EVENTO.get(f["evento"], f["evento"])
            datos.append([fecha_hora(f["fecha"]), f["usuario"] or "-", cuenta, evento, f["detalle"] or ""])

        h.append(_tabla(
            ["Fecha", "Usuario", "Cuenta", "Evento", "Detalle"], datos,
            [2.6 * cm, 2.3 * cm, 3.4 * cm, 3.0 * cm, ANCHO_UTIL - 11.3 * cm],
            estilos=e,
        ))
    else:
        h.append(_p("Aún no hay eventos registrados.", e["vacio"]))

    doc.build(h, canvasmaker=partial(_CanvasNumerado, meta=meta))
    return ruta
