"""
Reporte en PDF de los articulos en stock (existencias actuales).

Recibe el diccionario de controlador_reportes.construir_reporte_existencias()
y reutiliza el encabezado, el pie, las tablas y los colores de reportes/pdf.py
para que ambos reportes se vean igual.
"""

from functools import partial

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, SimpleDocTemplate, Spacer, Table, TableStyle

from reportes.formato import dinero, entero, plural
from reportes.pdf import (
    ANCHO_UTIL, AVISO_SUAVE, BORDE, FONDO_ALT, MARGEN_X, PRIMARIO_SUAVE,
    _CanvasNumerado, _estilos, _p, _tabla,
)


def _indicadores(ind, e):
    tarjetas = [
        ("Artículos en stock", entero(ind["productos"]),
         f"de {entero(ind['productos_activos'])} productos activos"),
        ("Unidades en existencia", entero(ind["unidades"]),
         plural(ind["categorias"], "categoría", "categorías")),
        ("Valor al costo", dinero(ind["valor_costo"]), "precio de compra × existencia"),
        ("Valor a precio de venta", dinero(ind["valor_venta"]), "precio de venta × existencia"),
    ]
    ancho = ANCHO_UTIL / 4
    celdas = [Table([[_p(etiqueta, e["kpi_etiqueta"])], [_p(valor, e["kpi_valor"])], [_p(detalle, e["kpi_detalle"])]],
                    colWidths=[ancho - 0.5 * cm],
                    style=[("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                           ("TOPPADDING", (0, 0), (-1, -1), 1), ("BOTTOMPADDING", (0, 0), (-1, -1), 1)])
              for etiqueta, valor, detalle in tarjetas]
    tabla = Table([celdas], colWidths=[ancho] * 4)
    tabla.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.6, BORDE),
        ("INNERGRID", (0, 0), (-1, -1), 0.6, BORDE),
        ("BACKGROUND", (0, 0), (0, 0), PRIMARIO_SUAVE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 9),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tabla


def generar_pdf_existencias(reporte, ruta):
    e = _estilos()
    ind = reporte["indicadores"]
    generado = reporte["generado"]
    fecha_gen = generado.strftime("%d/%m/%Y")
    hora_gen = generado.strftime("%H:%M")

    meta = {
        "titulo_reporte": "Reporte de existencias",
        "periodo": f"Al {fecha_gen}",
        "pie": f"Generado el {fecha_gen} a las {hora_gen}"
               + (f" por {reporte['generado_por']}" if reporte.get("generado_por") else ""),
    }

    doc = SimpleDocTemplate(
        ruta, pagesize=A4,
        leftMargin=MARGEN_X, rightMargin=MARGEN_X, topMargin=2.6 * cm, bottomMargin=2.0 * cm,
        title=f"Reporte de existencias - {fecha_gen}",
        author="Tienda Jazmín", subject="Artículos en stock",
    )

    h = []
    h.append(_p("Reporte de artículos en stock", e["titulo"]))
    h.append(_p(f"Situación del inventario al {fecha_gen} a las {hora_gen}", e["subtitulo"]))
    h.append(Spacer(1, 12))
    h.append(_indicadores(ind, e))

    # --- Resumen por categoria ---
    categorias = reporte["por_categoria"]
    if categorias:
        filas = [[c["categoria"], entero(c["productos"]), entero(c["unidades"]),
                  dinero(c["valor_costo"]), dinero(c["valor_venta"])] for c in categorias]
        filas.append(["Total", entero(ind["productos"]), entero(ind["unidades"]),
                      dinero(ind["valor_costo"]), dinero(ind["valor_venta"])])
        h.append(KeepTogether([
            _p("Resumen por categoría", e["seccion"]),
            _tabla(["Categoría", "Artículos", "Unidades", "Valor al costo", "Valor de venta"], filas,
                   [ANCHO_UTIL - 12.4 * cm, 2.4 * cm, 2.4 * cm, 3.8 * cm, 3.8 * cm],
                   derecha=(1, 2, 3, 4), estilos=e,
                   resaltar=lambda i: PRIMARIO_SUAVE if i == len(filas) - 1 else None),
        ]))

    # --- Detalle de articulos ---
    productos = reporte["productos"]
    h.append(_p("Detalle de artículos en stock", e["seccion"]))
    if productos:
        h.append(_p("Ordenados por categoría y nombre. Las filas resaltadas tienen una existencia "
                    "igual o menor a su stock mínimo.", e["nota"]))
        h.append(Spacer(1, 6))
        filas = [[p["codigo"], p["nombre"], p["nombre_categoria"], p["unidad_medida"] or "",
                  entero(p["existencia"]), entero(p["stock_minimo"]), dinero(p["precio_venta"]),
                  dinero(p["precio_venta"] * p["existencia"])] for p in productos]
        h.append(_tabla(["Código", "Producto", "Categoría", "Unidad", "Existencia", "Mínimo", "Precio", "Valor"],
                        filas,
                        [1.7 * cm, ANCHO_UTIL - 14.0 * cm, 2.4 * cm, 1.9 * cm, 2.1 * cm, 1.7 * cm, 2.0 * cm, 2.2 * cm],
                        derecha=(4, 5, 6, 7), estilos=e,
                        resaltar=lambda i: AVISO_SUAVE if productos[i]["stock_bajo"] else None))
    else:
        h.append(_p("No hay artículos con existencia en este momento.", e["vacio"]))

    if ind["sin_existencia"]:
        h.append(Spacer(1, 10))
        caja = Table([[_p(f"Además hay {plural(ind['sin_existencia'], 'producto activo', 'productos activos')} "
                          "sin existencia que no aparecen en este reporte.", e["nota"])]],
                     colWidths=[ANCHO_UTIL])
        caja.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), FONDO_ALT),
            ("BOX", (0, 0), (-1, -1), 0.6, BORDE),
            ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        h.append(caja)

    doc.build(h, canvasmaker=partial(_CanvasNumerado, meta=meta))
    return ruta
