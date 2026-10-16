"""
Pantalla de Reportes.

Flujo: elegir periodo -> consultar (en segundo plano) -> actualizar
indicadores, graficos y tablas -> Generar PDF (dialogo "Guardar reporte").

La pantalla solo presenta datos: las consultas estan en models/reportes.py,
el calculo en controllers/controlador_reportes.py y el PDF en reportes/pdf.py.
El PDF se genera con el MISMO reporte que se esta mostrando.
"""

import os
from datetime import date

from PySide6.QtCore import QDate, QLocale, QStandardPaths, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDateEdit, QFileDialog, QHBoxLayout, QSpinBox,
    QStackedWidget, QWidget,
)

from controllers import controlador_reportes
from helpers import permisos
from reportes.formato import (
    ETIQUETA_OPERACION, ETIQUETA_PAGO, dinero, entero, plural, variacion,
)
from reportes.periodos import MESES, TIPOS, ETIQUETAS, crear_periodo
from ui import theme
from ui.formato_ui import fecha_corta
from ui.widgets import messages
from ui.widgets.charts import BarChart, DonutChart, HorizontalBars
from ui.widgets.common import Card, button, label
from ui.widgets.data_table import Column, DataTable
from ui.widgets.forms import SearchField, choice_combo
from ui.widgets.page import Page
from ui.widgets.responsive import ResponsiveGrid
from ui.widgets.stat_card import StatCard
from ui.widgets.tarea import Tarea

_LOCALE_ES = QLocale(QLocale.Language.Spanish, QLocale.Country.ElSalvador)

COLORES_PAGO = {
    "efectivo": theme.PRIMARY,
    "tarjeta": theme.INFO,
    "otro": theme.TEXT_SUBTLE,
    "credito": theme.WARNING,
}

_BADGE_OPERACION = {"venta": "neutral", "entrada": "success", "salida": "info", "ajuste": "warning"}


def _dinero_eje(centavos):
    return f"${centavos / 100:,.0f}" if centavos < 100_000_00 else f"${centavos / 100_000:,.0f}k"


class ReportesPage(Page):
    def __init__(self, navigate):
        super().__init__("Reportes", "Analiza las operaciones de un período y genera el reporte en PDF.")
        self.navigate = navigate
        self._reporte = None
        self._consulta_n = 0
        self._tareas = set()
        self._pdf_pendiente = False
        self._fecha = date.today()

        self.boton_actualizar = self.add_action(
            button("Actualizar", "refresh", "secondary", on_click=self._consultar_ahora,
                   tooltip="Volver a leer los datos del período (F5)"))
        self.boton_existencias = self.add_action(
            button("PDF de existencias", "box", "secondary", on_click=self._generar_pdf_existencias,
                   tooltip="Guardar en PDF los artículos que hay en stock ahora"))
        self.boton_pdf = self.add_action(
            button("Generar PDF", "file", "primary", large=True, on_click=self._generar_pdf))
        self.boton_pdf.setEnabled(False)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(350)
        self._debounce.timeout.connect(self._consultar_ahora)

        self.content.addWidget(self._crear_selector())

        self.aviso_vacio = label("No hay operaciones registradas durante el período seleccionado.", "info", wrap=True)
        self.aviso_vacio.hide()
        self.content.addWidget(self.aviso_vacio)

        self.content.addWidget(self._crear_indicadores())

        self.card_resumen = Card("Resumen del período")
        self.texto_resumen = label("", wrap=True)
        self.texto_resumen.setStyleSheet("font-size: 15px; line-height: 150%;")
        self.texto_resumen.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.card_resumen.body.addWidget(self.texto_resumen)
        self.content.addWidget(self.card_resumen)

        self._crear_graficos()
        self._crear_rankings()
        self._crear_detalle()
        self._sincronizar_controles(self._fecha)

    # ------------------------------------------------------------------
    # Selector de periodo
    # ------------------------------------------------------------------

    def _crear_selector(self):
        tarjeta = Card("Período del reporte")

        fila_tipos = QHBoxLayout()
        fila_tipos.setSpacing(8)
        self.grupo_tipo = QButtonGroup(self)
        self._botones_tipo = {}
        for tipo in TIPOS:
            boton = button(ETIQUETAS[tipo], variant="secondary")
            boton.setCheckable(True)
            boton.setProperty("segment", True)
            boton.setProperty("tipo", tipo)
            boton.setMinimumWidth(110)
            self.grupo_tipo.addButton(boton)
            self._botones_tipo[tipo] = boton
            fila_tipos.addWidget(boton)
        fila_tipos.addStretch(1)
        self._botones_tipo["mensual"].setChecked(True)
        self.grupo_tipo.buttonClicked.connect(self._al_cambiar_tipo)
        tarjeta.body.addLayout(fila_tipos)

        fila = QHBoxLayout()
        fila.setSpacing(10)
        self.boton_anterior = button("", "chevron-left", "secondary", tooltip="Período anterior",
                                     on_click=lambda: self._mover(-1))
        self.boton_siguiente = button("", "chevron-right", "secondary", tooltip="Período siguiente",
                                      on_click=lambda: self._mover(1))
        for b in (self.boton_anterior, self.boton_siguiente):
            b.setFixedWidth(48)

        # Controles de fecha segun el tipo
        self.stack_fecha = QStackedWidget()

        self.fecha_dia = self._crear_date_edit()
        self.fecha_semana = self._crear_date_edit()

        pagina_mes = QWidget()
        fila_mes = QHBoxLayout(pagina_mes)
        fila_mes.setContentsMargins(0, 0, 0, 0)
        fila_mes.setSpacing(8)
        self.combo_mes = QComboBox()
        self.combo_mes.addItems([m.capitalize() for m in MESES])
        self.combo_mes.setMinimumWidth(150)
        self.anio_mes = self._crear_anio()
        fila_mes.addWidget(self.combo_mes)
        fila_mes.addWidget(self.anio_mes)

        self.anio_solo = self._crear_anio()

        self._paginas_fecha = {"diario": self.fecha_dia, "semanal": self.fecha_semana,
                               "mensual": pagina_mes, "anual": self.anio_solo}
        for widget in self._paginas_fecha.values():
            self.stack_fecha.addWidget(widget)

        for control, senal in ((self.fecha_dia, "dateChanged"), (self.fecha_semana, "dateChanged"),
                               (self.combo_mes, "currentIndexChanged"), (self.anio_mes, "valueChanged"),
                               (self.anio_solo, "valueChanged")):
            getattr(control, senal).connect(self._al_cambiar_fecha)

        fila.addWidget(self.boton_anterior)
        fila.addWidget(self.stack_fecha)
        fila.addWidget(self.boton_siguiente)
        fila.addSpacing(8)
        self.rango = label("", "muted")
        self.rango.setStyleSheet("font-size: 15px;")
        fila.addWidget(self.rango, 1)
        self.estado = label("", "caption")
        fila.addWidget(self.estado)
        self.boton_consultar = button("Consultar", "search", "primary", on_click=self._consultar_ahora)
        fila.addWidget(self.boton_consultar)
        tarjeta.body.addLayout(fila)
        return tarjeta

    def _crear_date_edit(self):
        campo = QDateEdit()
        campo.setCalendarPopup(True)
        campo.setDisplayFormat("dd/MM/yyyy")
        campo.setLocale(_LOCALE_ES)
        campo.calendarWidget().setLocale(_LOCALE_ES)
        campo.calendarWidget().setFirstDayOfWeek(Qt.Monday)
        campo.setMinimumWidth(170)
        return campo

    def _crear_anio(self):
        campo = QSpinBox()
        campo.setRange(2000, 2100)
        campo.setMinimumWidth(110)
        campo.setLocale(QLocale.c())
        return campo

    def _tipo(self):
        boton = self.grupo_tipo.checkedButton()
        return boton.property("tipo") if boton else "mensual"

    def _fecha_de_controles(self):
        tipo = self._tipo()
        if tipo == "diario":
            return self.fecha_dia.date().toPython()
        if tipo == "semanal":
            return self.fecha_semana.date().toPython()
        if tipo == "mensual":
            return date(self.anio_mes.value(), self.combo_mes.currentIndex() + 1, 1)
        return date(self.anio_solo.value(), 1, 1)

    def _sincronizar_controles(self, fecha):
        """Pone todos los controles en la fecha dada, sin disparar consultas."""
        controles = (self.fecha_dia, self.fecha_semana, self.combo_mes, self.anio_mes, self.anio_solo)
        for c in controles:
            c.blockSignals(True)
        qfecha = QDate(fecha.year, fecha.month, fecha.day)
        self.fecha_dia.setDate(qfecha)
        self.fecha_semana.setDate(qfecha)
        self.combo_mes.setCurrentIndex(fecha.month - 1)
        self.anio_mes.setValue(fecha.year)
        self.anio_solo.setValue(fecha.year)
        for c in controles:
            c.blockSignals(False)
        self._fecha = fecha
        self.stack_fecha.setCurrentWidget(self._paginas_fecha[self._tipo()])
        self._actualizar_rango()

    def _periodo_elegido(self):
        return crear_periodo(self._tipo(), self._fecha)

    def _actualizar_rango(self):
        periodo = self._periodo_elegido()
        self.rango.setText(periodo.rango_texto)
        # No tiene sentido avanzar a periodos que aun no empiezan.
        self.boton_siguiente.setEnabled(periodo.siguiente().inicio <= date.today())

    def _al_cambiar_tipo(self, *_):
        self._sincronizar_controles(self._fecha)
        self._consultar_ahora()

    def _al_cambiar_fecha(self, *_):
        self._fecha = self._fecha_de_controles()
        self._actualizar_rango()
        self._debounce.start()

    def _mover(self, pasos):
        periodo = self._periodo_elegido()
        nuevo = periodo.anterior() if pasos < 0 else periodo.siguiente()
        self._sincronizar_controles(nuevo.inicio)
        self._consultar_ahora()

    # ------------------------------------------------------------------
    # Construccion del dashboard
    # ------------------------------------------------------------------

    def _crear_indicadores(self):
        # Fila 1: ventas (valor de lo vendido) y cobros.  Fila 2: dinero recibido e inventario.
        self.card_ventas = StatCard("Ventas totales", "cart", "primary")
        self.card_contado = StatCard("Ventas al contado", "dollar", "success")
        self.card_credito = StatCard("Ventas a crédito", "wallet", "warning")
        self.card_cobros = StatCard("Cobros de créditos", "receipt", "info")
        self.card_recibido = StatCard("Dinero recibido", "check", "success")
        self.card_recibido.setStyleSheet(f"QFrame[card=\"true\"] {{ background: {theme.PRIMARY_SOFT}; "
                                         f"border-color: {theme.PRIMARY_LIGHT}; }}")
        self.card_recibido.setToolTip("Ventas al contado + cobros de créditos del período")
        self.card_entradas = StatCard("Entradas (unidades)", "arrow-in", "success")
        self.card_salidas = StatCard("Salidas manuales (unidades)", "arrow-out", "info")
        self.card_stock = StatCard("Stock bajo", "alert", "warning", clickable=permisos.puede_ver("inventario"))
        self.card_stock.clicked.connect(lambda: self.navigate("inventario"))

        rejilla = ResponsiveGrid([(1080, 4), (560, 2), (0, 1)])
        for tarjeta in (self.card_ventas, self.card_contado, self.card_credito, self.card_cobros,
                        self.card_recibido, self.card_entradas, self.card_salidas, self.card_stock):
            rejilla.add(tarjeta)
        return rejilla

    def _crear_graficos(self):
        self.card_ventas_graf = Card("Ventas y dinero recibido", "Por día.")
        self.grafico_ventas = BarChart([("Ventas", theme.PRIMARY_LIGHT), ("Dinero recibido", theme.PRIMARY)],
                                       formato=_dinero_eje, altura=290,
                                       vacio="No hay ventas ni cobros registrados en este período.",
                                       formato_tooltip=dinero)
        self.card_ventas_graf.body.addWidget(self.grafico_ventas)
        self.content.addWidget(self.card_ventas_graf)

        card_mov = Card("Entradas vs. salidas", "Unidades que entraron y salieron del inventario (las salidas incluyen ventas).")
        self.grafico_mov = BarChart([("Entradas", theme.SUCCESS), ("Salidas", theme.INFO)], altura=260,
                                    vacio="No hubo movimientos de inventario en este período.")
        card_mov.body.addWidget(self.grafico_mov)

        card_pago = Card("Ventas por método de pago", "Monto vendido con cada forma de pago.")
        self.grafico_pago = DonutChart(formato=dinero, altura=260, vacio="No hay ventas en este período.")
        card_pago.body.addWidget(self.grafico_pago)

        rejilla = ResponsiveGrid([(1000, 2), (0, 1)])
        rejilla.add(card_mov, 3)
        rejilla.add(card_pago, 2)
        self.content.addWidget(rejilla)

    def _crear_rankings(self):
        card_top = Card("Productos más vendidos", "Unidades vendidas en el período.")
        self.grafico_top = HorizontalBars(theme.PRIMARY, vacio="No hubo ventas en este período.")
        card_top.body.addWidget(self.grafico_top)
        card_top.body.addStretch(1)

        card_mov = Card("Productos con mayor movimiento", "Suma de unidades que entraron y salieron.")
        self.tabla_movimiento = DataTable(
            [
                Column("nombre", "Producto", stretch=True),
                Column("entradas", "Entradas", align="center", width=100),
                Column("salidas", "Salidas", align="center", width=100),
                Column("total", "Total", align="center", width=90),
            ],
            empty_text="No hubo movimientos de inventario en este período.",
            min_height=300,
        )
        card_mov.body.addWidget(self.tabla_movimiento)

        rejilla = ResponsiveGrid([(1000, 2), (0, 1)])
        rejilla.add(card_top)
        rejilla.add(card_mov)
        self.content.addWidget(rejilla)

        self.content.addWidget(self._crear_creditos())

        card_bajo = Card("Productos con stock bajo",
                         "Situación actual: existencia igual o menor al stock mínimo (no depende del período).")
        self.tabla_bajo = DataTable(
            [
                Column("codigo", "Código", width=130),
                Column("nombre", "Producto", stretch=True),
                Column("existencia", "Existencia", align="center", width=120),
                Column("stock_minimo", "Stock mínimo", align="center", width=130),
            ],
            empty_text="Ningún producto está por debajo de su stock mínimo.",
            highlight=lambda f: "danger" if f["existencia"] == 0 else "warning",
            min_height=180,
        )
        card_bajo.body.addWidget(self.tabla_bajo)
        self.content.addWidget(card_bajo)

    def _crear_creditos(self):
        card = Card("Créditos y cobros del período",
                    "Una venta a crédito cuenta como dinero recibido solo cuando el cliente paga.")
        if permisos.puede_ver("creditos"):
            card.add_header_widget(button("Ir a créditos", variant="ghost",
                                          on_click=lambda: self.navigate("creditos")))
        self.texto_creditos = label("", "info", wrap=True)
        card.body.addWidget(self.texto_creditos)
        self.tabla_cobros = DataTable(
            [
                Column("fecha", "Fecha", fmt=fecha_corta, width=150),
                Column("numero_venta", "Crédito", width=120),
                Column("nombre_completo", "Cliente", stretch=True),
                Column("metodo_pago", "Método", align="center", width=120,
                       fmt=lambda v: ETIQUETA_PAGO.get(v, v or "Otro")),
                Column("monto", "Monto", fmt=dinero, align="right", width=130),
            ],
            empty_text="No se recibieron pagos de créditos en este período.",
            min_height=200,
        )
        card.body.addWidget(self.tabla_cobros)
        return card

    def _crear_detalle(self):
        card = Card("Detalle del período", "Todas las operaciones de inventario, las más recientes primero.")
        filtros = QHBoxLayout()
        filtros.setSpacing(10)
        self.buscador = SearchField("Buscar producto, venta o motivo")
        self.buscador.textChanged.connect(self._filtrar_detalle)
        filtros.addWidget(self.buscador, 2)
        self.filtro_operacion = choice_combo([("Todas las operaciones", None), ("Ventas", "venta"),
                                              ("Entradas", "entrada"), ("Salidas manuales", "salida"),
                                              ("Ajustes", "ajuste")])
        self.filtro_operacion.setMinimumWidth(210)
        self.filtro_operacion.currentIndexChanged.connect(self._filtrar_detalle)
        filtros.addWidget(self.filtro_operacion)
        filtros.addStretch(1)
        card.body.addLayout(filtros)

        self.tabla_detalle = DataTable(
            [
                Column("fecha", "Fecha", fmt=fecha_corta, width=150),
                Column("operacion", "Operación", align="center", width=120,
                       badge=lambda f: (ETIQUETA_OPERACION.get(f["operacion"], f["operacion"]),
                                        _BADGE_OPERACION.get(f["operacion"], "neutral"))),
                Column("producto", "Producto", stretch=True,
                       value=lambda f: f"{f['codigo']} - {f['producto']}"),
                Column("cantidad", "Cantidad", align="center", width=100),
                Column("existencia_nueva", "Existencia resultante", align="center", width=170),
                Column("referencia", "Referencia", width=200,
                       value=lambda f: (f"{f['numero_venta']} ({ETIQUETA_PAGO.get(f['tipo_pago'], '')})"
                                        if f["numero_venta"] else (f["descripcion"] or ""))),
            ],
            empty_text="No hay operaciones registradas durante el período seleccionado.",
            empty_filtered_text="No hay operaciones con esos filtros.",
            min_height=380,
        )
        card.body.addWidget(self.tabla_detalle, 1)
        self.nota_detalle = label("", "caption")
        card.body.addWidget(self.nota_detalle)
        self.content.addWidget(card, 1)

    # ------------------------------------------------------------------
    # Consulta
    # ------------------------------------------------------------------

    def refresh(self):
        """Al entrar a la seccion se vuelve a consultar el periodo elegido."""
        self._consultar_ahora()

    def _consultar_ahora(self):
        self._debounce.stop()
        self._fecha = self._fecha_de_controles()
        self._consulta_n += 1
        tarea = Tarea(("consulta", self._consulta_n), controlador_reportes.generar_reporte,
                      self._tipo(), self._fecha, parent=self)
        self._lanzar(tarea)
        self.estado.setText("Consultando...")
        self.boton_consultar.setEnabled(False)

    def _lanzar(self, tarea):
        self._tareas.add(tarea)
        tarea.terminado.connect(self._al_terminar_tarea)
        tarea.finished.connect(lambda t=tarea: self._tareas.discard(t))
        tarea.finished.connect(tarea.deleteLater)
        tarea.start()

    def _al_terminar_tarea(self, etiqueta, resultado):
        tipo, dato = etiqueta
        if tipo == "consulta":
            self._al_recibir_reporte(dato, resultado)
        elif tipo == "pdf":
            self._al_terminar_pdf(dato, resultado)
        elif tipo == "existencias":
            self._al_terminar_pdf_existencias(dato, resultado)

    def _al_recibir_reporte(self, numero, resultado):
        if numero != self._consulta_n:
            return  # llego tarde: ya hay una consulta mas nueva
        self.estado.setText("")
        self.boton_consultar.setEnabled(True)

        if isinstance(resultado, Exception):
            exito, mensaje, reporte = False, "No se pudo consultar la información del período.", None
        else:
            exito, mensaje, reporte = resultado
        if not exito:
            self._pdf_pendiente = False
            messages.error(self, "No se pudo generar el reporte", mensaje)
            return

        self._reporte = reporte
        self._mostrar(reporte)
        self.boton_pdf.setEnabled(True)
        if self._pdf_pendiente:
            self._pdf_pendiente = False
            self._generar_pdf()

    # ------------------------------------------------------------------
    # Mostrar datos
    # ------------------------------------------------------------------

    def _mostrar(self, r):
        ind = r["indicadores"]
        ant = r["anterior"]
        periodo = r["periodo"]

        self.aviso_vacio.setVisible(r["vacio"])
        self.aviso_vacio.setText(f"No hay operaciones registradas durante {periodo.frase}.")

        self.card_ventas.set_value(dinero(ind["monto_ventas"]),
                                   f"{plural(ind['ventas'], 'venta', 'ventas')}, "
                                   f"{variacion(ind['monto_ventas'], ant['monto_ventas'])}")
        self.card_contado.set_value(dinero(ind["monto_contado"]), plural(ind["ventas_contado"], "venta", "ventas"))
        self.card_credito.set_value(dinero(ind["monto_credito"]),
                                    plural(ind["ventas_credito"], "venta", "ventas") + ", aún no es dinero recibido")
        self.card_cobros.set_value(dinero(ind["monto_cobros"]), plural(ind["cobros"], "pago recibido", "pagos recibidos"))
        self.card_recibido.set_value(dinero(ind["dinero_recibido"]),
                                     "contado + cobros, " + variacion(ind["dinero_recibido"], ant["dinero_recibido"])
                                     .replace("sin ventas", "sin ingresos"))
        self.card_entradas.set_value(entero(ind["entradas"]), plural(ind["entradas_mov"], "movimiento", "movimientos"))
        self.card_salidas.set_value(entero(ind["salidas"]),
                                    plural(ind["salidas_mov"], "movimiento", "movimientos") + ", sin contar ventas")
        self.card_stock.set_value(entero(ind["stock_bajo"]),
                                  f"de {entero(ind['productos_activos'])} productos activos (situación actual)")

        cred = r["credito"]
        est = cred["estados"]
        texto = (f"Créditos otorgados en el período: {entero(cred['otorgados'])} por {dinero(cred['monto'])}. "
                 f"Estado hoy: {entero(est['pendiente'])} pendientes, {entero(est['parcial'])} parciales y "
                 f"{entero(est['pagado'])} pagados. Cobros recibidos: {dinero(cred['cobros']['monto'])}. "
                 f"Saldo pendiente total hoy: {dinero(cred['pendiente_actual']['total'])} en "
                 f"{plural(cred['activos_hoy'], 'crédito activo', 'créditos activos')}.")
        self.texto_creditos.setText(texto)
        self.tabla_cobros.set_rows(cred["pagos"])

        self.texto_resumen.setText(r["resumen"])

        series = r["series"]
        self.card_ventas_graf.subtitle_label.setText(
            f"Por {series['unidad']}: lo vendido frente a lo que realmente se cobró (contado + pagos de créditos). "
            "Pasa el mouse sobre una barra para ver los montos.")
        self.grafico_ventas.set_data(series["etiquetas"], [series["ventas_monto"], series["recibido"]])
        self.grafico_mov.set_data(series["etiquetas"], [series["entradas"], series["salidas"]])
        self.grafico_pago.set_data([
            (ETIQUETA_PAGO[m["tipo_pago"]], m["monto"], COLORES_PAGO[m["tipo_pago"]],
             f"{dinero(m['monto'])} en {plural(m['ventas'], 'venta', 'ventas')}")
            for m in r["metodos"]
        ])
        self.grafico_top.set_data([
            (t["nombre"], t["unidades"], f"{entero(t['unidades'])} u.  {dinero(t['ingresos'])}")
            for t in r["mas_vendidos"][:8]
        ])

        self.tabla_movimiento.set_rows(r["mayor_movimiento"])
        self.tabla_bajo.set_rows(r["stock_bajo"])
        self.tabla_detalle.set_rows(r["detalle"])
        self._filtrar_detalle()
        if r["detalle_total"] > len(r["detalle"]):
            self.nota_detalle.setText(f"Se muestran las {entero(len(r['detalle']))} operaciones más recientes "
                                      f"de {entero(r['detalle_total'])}.")
        else:
            self.nota_detalle.setText(
                plural(r["detalle_total"], "movimiento de inventario", "movimientos de inventario")
                + f" en el período ({plural(ind['operaciones'], 'operación', 'operaciones')} en total, contando cobros).")

        self.boton_pdf.setToolTip(f"Guardar en PDF: {periodo.titulo}")

    def _filtrar_detalle(self, *_):
        operacion = self.filtro_operacion.currentData()
        self.tabla_detalle.set_predicate(lambda f: operacion is None or f["operacion"] == operacion)
        self.tabla_detalle.set_filter_text(self.buscador.text())

    # ------------------------------------------------------------------
    # PDF
    # ------------------------------------------------------------------

    def _generar_pdf(self):
        # Si el periodo de los controles no es el que se esta mostrando, primero se consulta.
        elegido = crear_periodo(self._tipo(), self._fecha_de_controles())
        if self._reporte is None or self._reporte["periodo"] != elegido or self._debounce.isActive():
            self._pdf_pendiente = True
            self._consultar_ahora()
            return

        periodo = self._reporte["periodo"]
        carpeta = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or os.path.expanduser("~")
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar reporte", os.path.join(carpeta, periodo.nombre_archivo), "Documento PDF (*.pdf)")
        if not ruta:
            return
        if not ruta.lower().endswith(".pdf"):
            ruta += ".pdf"

        self.boton_pdf.setEnabled(False)
        self.boton_pdf.setText("Generando PDF...")
        self._lanzar(Tarea(("pdf", ruta), controlador_reportes.exportar_pdf, self._reporte, ruta, parent=self))

    def _generar_pdf_existencias(self):
        carpeta = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation) or os.path.expanduser("~")
        nombre = f"existencias_{date.today():%Y-%m-%d}.pdf"
        ruta, _ = QFileDialog.getSaveFileName(
            self, "Guardar reporte de existencias", os.path.join(carpeta, nombre), "Documento PDF (*.pdf)")
        if not ruta:
            return
        if not ruta.lower().endswith(".pdf"):
            ruta += ".pdf"

        self.boton_existencias.setEnabled(False)
        self.boton_existencias.setText("Generando PDF...")
        self._lanzar(Tarea(("existencias", ruta), controlador_reportes.exportar_pdf_existencias, ruta, parent=self))

    def _al_terminar_pdf_existencias(self, ruta, resultado):
        self.boton_existencias.setEnabled(True)
        self.boton_existencias.setText("PDF de existencias")
        self._avisar_pdf_guardado(ruta, resultado)

    def _al_terminar_pdf(self, ruta, resultado):
        self.boton_pdf.setEnabled(True)
        self.boton_pdf.setText("Generar PDF")
        self._avisar_pdf_guardado(ruta, resultado)

    def _avisar_pdf_guardado(self, ruta, resultado):
        if isinstance(resultado, Exception):
            exito, mensaje = False, "No se pudo generar el PDF."
        else:
            exito, mensaje = resultado
        if not exito:
            messages.error(self, "No se pudo guardar el reporte", mensaje)
            return
        messages.success(self, "Reporte PDF guardado.")
        if messages.confirm(self, "Reporte guardado",
                            f"El archivo se guardó en:\n{ruta}\n\n¿Quieres abrirlo ahora?",
                            confirmar="Abrir PDF", cancelar="Cerrar"):
            QDesktopServices.openUrl(QUrl.fromLocalFile(ruta))
