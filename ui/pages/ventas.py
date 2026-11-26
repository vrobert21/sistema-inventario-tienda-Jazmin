"""
Pantalla de Ventas.

Usa, sin cambios:
  controlador_ventas.obtener_productos_para_venta()
  controlador_ventas.registrar_venta(tipo_pago, id_cliente, items)
  controlador_ventas.obtener_ventas_recientes()
  controlador_clientes.obtener_lista_clientes()

Mejora respecto a la version anterior: si se agrega el mismo producto
dos veces, se suma a la linea existente en lugar de crear otra. Ademas
de ser mas claro, evita un problema del modelo: con dos lineas del
mismo producto, models/venta.py calcula la existencia final de cada
linea desde la misma existencia inicial y la segunda sobrescribe a la
primera (solo se descontaba la ultima cantidad).
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

from controllers import controlador_clientes, controlador_ventas
from helpers import permisos
from helpers.formato import centavos_a_texto
from ui.formato_ui import METODOS_PAGO, etiqueta_pago, fecha_corta, plural
from ui.widgets import messages
from ui.widgets.common import Card, button, label
from ui.widgets.data_table import Column, DataTable
from ui.widgets.forms import FormField, SearchField, SearchableCombo, choice_combo, int_input
from ui.widgets.page import Page
from ui.widgets.responsive import ResponsiveGrid


class VentasPage(Page):
    def __init__(self, navigate):
        super().__init__("Ventas", "Agrega productos al carrito, elige el método de pago y registra la venta.")
        self.navigate = navigate
        self._carrito = []              # [{id_producto, nombre, cantidad, precio_unitario, subtotal}]
        self._productos = {}            # id_producto -> fila de producto disponible

        zona = ResponsiveGrid([(1100, 2), (0, 1)], spacing=20)
        zona.add(self._crear_carrito(), 3)
        zona.add(self._crear_cobro(), 2)
        self.content.addWidget(zona)
        self.content.addWidget(self._crear_recientes(), 1)

    # ------------------------------------------------------------------
    # Construccion
    # ------------------------------------------------------------------

    def _crear_carrito(self):
        tarjeta = Card("Productos de la venta")

        fila = QHBoxLayout()
        fila.setSpacing(12)
        self.combo_producto = SearchableCombo("Escribe el código o nombre del producto")
        self.combo_producto.currentIndexChanged.connect(self._al_elegir_producto)
        self.combo_producto.lineEdit().textChanged.connect(self._al_elegir_producto)
        self.campo_producto = FormField("Producto", self.combo_producto)
        fila.addWidget(self.campo_producto, 1)

        self.entrada_cantidad = int_input(1, 1_000_000)
        self.entrada_cantidad.setValue(1)
        self.entrada_cantidad.setMinimumWidth(110)
        self.entrada_cantidad.lineEdit().returnPressed.connect(self._agregar)
        fila.addWidget(FormField("Cantidad", self.entrada_cantidad))

        self.boton_agregar = button("Agregar", "plus", "secondary", on_click=self._agregar,
                                    tooltip="Agregar al carrito (Enter en Cantidad)")
        fila.addWidget(self.boton_agregar, 0, Qt.AlignBottom)
        tarjeta.body.addLayout(fila)

        self.info_producto = label("Elige un producto para ver su precio y existencia.", "info", wrap=True)
        tarjeta.body.addWidget(self.info_producto)

        self.tabla_carrito = DataTable(
            [
                Column("nombre", "Producto", stretch=True),
                Column("cantidad", "Cantidad", align="center", width=100),
                Column("precio_unitario", "Precio", fmt=centavos_a_texto, align="right", width=110),
                Column("subtotal", "Subtotal", fmt=centavos_a_texto, align="right", width=120),
            ],
            empty_text="El carrito está vacío. Busca un producto arriba y pulsa \"Agregar\".",
            min_height=240,
        )
        self.tabla_carrito.selection_changed.connect(
            lambda f: self.boton_quitar.setEnabled(f is not None))
        tarjeta.body.addWidget(self.tabla_carrito, 1)

        acciones = QHBoxLayout()
        acciones.setSpacing(8)
        self.boton_quitar = button("Quitar producto", "trash", "ghost", on_click=self._quitar)
        self.boton_quitar.setEnabled(False)
        self.boton_vaciar = button("Vaciar carrito", "x", "ghost", on_click=self._vaciar)
        acciones.addWidget(self.boton_quitar)
        acciones.addWidget(self.boton_vaciar)
        acciones.addStretch(1)
        tarjeta.body.addLayout(acciones)
        return tarjeta

    def _crear_cobro(self):
        tarjeta = Card("Cobro")
        tarjeta.body.setSpacing(16)

        totales = QVBoxLayout()
        totales.setSpacing(0)
        totales.addWidget(label("Total a cobrar", "statLabel"))
        self.etiqueta_total = label("$0.00", "bigTotal")
        totales.addWidget(self.etiqueta_total)
        self.etiqueta_items = label("Sin productos", "caption")
        totales.addWidget(self.etiqueta_items)
        tarjeta.body.addLayout(totales)

        self.combo_pago = choice_combo(METODOS_PAGO)
        self.combo_pago.currentIndexChanged.connect(self._al_cambiar_pago)
        tarjeta.body.addWidget(FormField("Método de pago", self.combo_pago))

        self.combo_cliente = SearchableCombo("Sin cliente")
        self.campo_cliente = FormField("Cliente", self.combo_cliente,
                                       ayuda="Opcional en ventas de contado.")
        tarjeta.body.addWidget(self.campo_cliente)

        tarjeta.body.addStretch(1)
        self.boton_registrar = button("Registrar venta", "check", "primary", large=True,
                                      on_click=self._registrar_venta)
        tarjeta.body.addWidget(self.boton_registrar)
        return tarjeta

    def _crear_recientes(self):
        es_admin = permisos.es_admin()
        descripcion = ("Las últimas 20 ventas registradas. Doble clic en una venta para anularla."
                       if es_admin else "Las últimas 20 ventas registradas.")
        tarjeta = Card("Ventas recientes", descripcion)
        self.buscador = SearchField("Buscar venta o cliente")
        self.buscador.textChanged.connect(lambda t: self.tabla_recientes.set_filter_text(t))
        tarjeta.add_header_widget(self.buscador)
        self.tabla_recientes = DataTable(
            [
                Column("numero_venta", "No. venta", width=120),
                Column("fecha", "Fecha", fmt=fecha_corta, width=160),
                Column("nombre_cliente", "Cliente", stretch=True,
                       fmt=lambda v: v or "Sin cliente"),
                Column("tipo_pago", "Método de pago", align="center", width=150,
                       badge=lambda f: (etiqueta_pago(f["tipo_pago"]),
                                        "info" if f["tipo_pago"] == "credito" else "neutral")),
                Column("nombre_usuario", "Atendió", width=150),
                Column("total", "Total", fmt=centavos_a_texto, align="right", width=120),
                Column("estado", "Estado", align="center", width=110,
                       badge=lambda f: (("Activa", "success") if f["estado"]
                                        else ("Anulada", "danger"))),
            ],
            empty_text="Todavía no hay ventas registradas.",
            empty_filtered_text="No hay ventas que coincidan con la búsqueda.",
            min_height=260,
        )
        if es_admin:
            self.tabla_recientes.row_activated.connect(self._anular_venta)
        tarjeta.body.addWidget(self.tabla_recientes, 1)
        return tarjeta

    # ------------------------------------------------------------------
    # Datos
    # ------------------------------------------------------------------

    def refresh(self):
        productos = controlador_ventas.obtener_productos_para_venta()
        self._productos = {p["id_producto"]: dict(p) for p in productos}
        self.combo_producto.set_items(
            [(f"{p['codigo']} - {p['nombre']}", p["id_producto"]) for p in productos])

        # Si algun producto del carrito ya no esta disponible, se avisa al registrar
        # (el modelo vuelve a validar existencia y estado).
        clientes = [c for c in controlador_clientes.obtener_lista_clientes() if c["estado"] == 1]
        self.combo_cliente.set_items([(c["nombre_completo"], c["id_cliente"]) for c in clientes])

        self.tabla_recientes.set_rows(controlador_ventas.obtener_ventas_recientes())
        self.tabla_recientes.set_filter_text(self.buscador.text())
        self._al_elegir_producto()
        self._refrescar_carrito()

    def _cantidad_en_carrito(self, id_producto):
        return sum(l["cantidad"] for l in self._carrito if l["id_producto"] == id_producto)

    def _al_elegir_producto(self, *_):
        p = self._productos.get(self.combo_producto.current_data())
        if p is None:
            self.info_producto.setText("Elige un producto para ver su precio y existencia.")
            return
        en_carrito = self._cantidad_en_carrito(p["id_producto"])
        texto = (f"Precio: {centavos_a_texto(p['precio_venta'])}      "
                 f"Disponibles: {p['existencia']} {p['unidad_medida']}")
        if en_carrito:
            texto += f"      En el carrito: {en_carrito}"
        self.info_producto.setText(texto)

    def _al_cambiar_pago(self, *_):
        es_credito = self.combo_pago.currentData() == "credito"
        self.campo_cliente.help.setText(
            "Obligatorio para ventas al crédito." if es_credito else "Opcional en ventas de contado.")
        if not es_credito:
            self.campo_cliente.set_invalid(False)

    # ------------------------------------------------------------------
    # Carrito
    # ------------------------------------------------------------------

    def _agregar(self):
        self.campo_producto.set_invalid(False)
        producto = self._productos.get(self.combo_producto.current_data())
        if producto is None:
            self.campo_producto.set_invalid(True)
            messages.warning(self, "Falta el producto", "Elige un producto de la lista para agregarlo al carrito.")
            self.combo_producto.setFocus()
            return

        cantidad = self.entrada_cantidad.value()
        if cantidad <= 0:
            messages.error(self, "Cantidad no válida", "La cantidad debe ser mayor a cero.")
            return

        ya_en_carrito = self._cantidad_en_carrito(producto["id_producto"])
        if ya_en_carrito + cantidad > producto["existencia"]:
            messages.error(
                self, "No hay existencia suficiente",
                f"Solo hay {producto['existencia']} unidades disponibles de "
                f"\"{producto['nombre']}\" (ya tienes {ya_en_carrito} en el carrito).",
            )
            return

        for linea in self._carrito:
            if linea["id_producto"] == producto["id_producto"]:
                linea["cantidad"] += cantidad
                linea["subtotal"] = linea["precio_unitario"] * linea["cantidad"]
                break
        else:
            self._carrito.append({
                "id_producto": producto["id_producto"],
                "nombre": producto["nombre"],
                "cantidad": cantidad,
                "precio_unitario": producto["precio_venta"],
                "subtotal": producto["precio_venta"] * cantidad,
            })

        self.entrada_cantidad.setValue(1)
        self._refrescar_carrito()
        self.tabla_carrito.select_by("id_producto", producto["id_producto"])
        self.combo_producto.setCurrentIndex(-1)
        self.combo_producto.lineEdit().clear()
        self.combo_producto.setFocus()

    def _quitar(self):
        fila = self.tabla_carrito.selected_row()
        if fila is None:
            messages.warning(self, "Selecciona un producto", "Haz clic en un producto del carrito para quitarlo.")
            return
        self._carrito = [l for l in self._carrito if l["id_producto"] != fila["id_producto"]]
        self._refrescar_carrito()

    def _vaciar(self):
        if not self._carrito:
            return
        if messages.confirm(self, "¿Vaciar el carrito?",
                            "Se quitarán todos los productos de esta venta.",
                            confirmar="Vaciar carrito", danger=True):
            self._carrito = []
            self._refrescar_carrito()

    def _refrescar_carrito(self):
        self.tabla_carrito.set_rows(self._carrito)
        total = sum(l["subtotal"] for l in self._carrito)
        unidades = sum(l["cantidad"] for l in self._carrito)
        self.etiqueta_total.setText(centavos_a_texto(total))
        self.etiqueta_items.setText(
            "Sin productos" if not self._carrito else
            f"{plural(len(self._carrito), 'producto', 'productos')}, "
            f"{plural(unidades, 'unidad', 'unidades')}")
        self.boton_vaciar.setEnabled(bool(self._carrito))
        self.boton_registrar.setEnabled(bool(self._carrito))
        self._al_elegir_producto()

    # ------------------------------------------------------------------
    # Registrar
    # ------------------------------------------------------------------

    def _registrar_venta(self):
        if not self._carrito:
            messages.warning(self, "Carrito vacío", "Agrega al menos un producto antes de registrar la venta.")
            return

        tipo_pago = self.combo_pago.currentData()
        id_cliente = self.combo_cliente.current_data()   # None = sin cliente

        if self.combo_cliente.currentText().strip() and id_cliente is None:
            self.campo_cliente.set_invalid(True)
            messages.warning(self, "Cliente no encontrado",
                             "Elige un cliente de la lista o deja el campo vacío.")
            return

        if tipo_pago == "credito" and id_cliente is None:
            self.campo_cliente.set_invalid(True)
            messages.error(self, "Falta el cliente",
                           "Debes seleccionar un cliente para registrar una venta al crédito.")
            self.combo_cliente.setFocus()
            return
        self.campo_cliente.set_invalid(False)

        total = sum(l["subtotal"] for l in self._carrito)
        cliente_texto = self.combo_cliente.currentText().strip() if id_cliente else "sin cliente"
        if not messages.confirm(
            self, "¿Registrar la venta?",
            f"Total {centavos_a_texto(total)}, pago con {etiqueta_pago(tipo_pago).lower()}, "
            f"{cliente_texto}.",
            confirmar="Registrar venta",
        ):
            return

        items = [{"id_producto": l["id_producto"], "cantidad": l["cantidad"]} for l in self._carrito]
        exito, mensaje, _resultado = controlador_ventas.registrar_venta(tipo_pago, id_cliente, items)

        if exito:
            messages.success(self, mensaje)
            self._carrito = []
            self.combo_pago.setCurrentIndex(0)
            self.combo_cliente.setCurrentIndex(-1)
            self.combo_cliente.lineEdit().clear()
            self.refresh()
        else:
            messages.error(self, "No se pudo registrar la venta", mensaje)
            # Los datos pueden haber cambiado (existencia, precio); se recargan
            # sin perder el carrito.
            self.refresh()

    # ------------------------------------------------------------------
    # Anular (solo administrador)
    # ------------------------------------------------------------------

    def _anular_venta(self, fila):
        if not fila["estado"]:
            messages.warning(self, "Venta ya anulada",
                             f"La venta {fila['numero_venta']} ya estaba anulada.")
            return
        if not messages.confirm(
            self, "¿Anular esta venta?",
            f"Se anulará la venta {fila['numero_venta']} por "
            f"{centavos_a_texto(fila['total'])}. El inventario vendido se regresará "
            "y, si era al crédito, se revertirá el cargo al cliente. Esta acción queda "
            "registrada en el historial de accesos.",
            confirmar="Anular venta", danger=True,
        ):
            return

        exito, mensaje = controlador_ventas.anular_venta(fila["id_venta"])
        if exito:
            messages.success(self, mensaje)
            self.refresh()
        else:
            messages.error(self, "No se pudo anular la venta", mensaje)
