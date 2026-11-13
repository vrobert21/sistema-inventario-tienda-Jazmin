"""
Pantalla de Categorias.

Usa: controlador_categorias.obtener_lista_categorias(),
     controlador_categorias.registrar_categoria(nombre),
     controlador_categorias.eliminar_categoria(id)
     + CategoriaDialog -> modificar_categoria
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout

from controllers import controlador_categorias
from ui import theme
from ui.dialogs.categoria_dialog import CategoriaDialog
from ui.formato_ui import badge_estado
from ui.widgets import messages
from ui.widgets.common import Card, button, label
from ui.widgets.data_table import Column, DataTable
from ui.widgets.forms import FormField, SearchField, text_input
from ui.widgets.page import Page


class CategoriasPage(Page):
    def __init__(self, navigate):
        super().__init__("Categorías", "Agrupa los productos para encontrarlos más rápido.")
        self.navigate = navigate

        # --- Formulario ---
        formulario = Card("Nueva categoría")
        fila = QHBoxLayout()
        fila.setSpacing(12)
        self.entrada_nombre = text_input("Ej. Bebidas, Abarrotes, Limpieza", 80)
        self.entrada_nombre.returnPressed.connect(self._registrar)
        self.campo_nombre = FormField("Nombre", self.entrada_nombre, requerido=True)
        fila.addWidget(self.campo_nombre, 1)
        self.boton_agregar = button("Agregar categoría", "plus", "primary", on_click=self._registrar)
        fila.addWidget(self.boton_agregar, 0, Qt.AlignBottom)
        formulario.body.addLayout(fila)
        self.error = label("", "caption")
        self.error.setStyleSheet(f"color: {theme.DANGER};")
        self.error.hide()
        formulario.body.addWidget(self.error)
        self.content.addWidget(formulario)

        # --- Listado ---
        listado = Card("Categorías registradas")
        self.buscador = SearchField("Buscar categoría")
        self.buscador.textChanged.connect(lambda t: self.tabla.set_filter_text(t))
        listado.add_header_widget(self.buscador)

        barra = QHBoxLayout()
        barra.setSpacing(10)
        barra.addStretch(1)
        self.boton_editar = button("Editar", "edit", "secondary", on_click=self._editar,
                                   tooltip="Cambiar el nombre de la categoría seleccionada (doble clic)")
        self.boton_eliminar = button("Eliminar", "trash", "danger", on_click=self._eliminar)
        barra.addWidget(self.boton_editar)
        barra.addWidget(self.boton_eliminar)
        listado.body.addLayout(barra)

        self.tabla = DataTable(
            [
                Column("nombre", "Nombre", stretch=True),
                Column("total_productos", "Productos", align="center", width=110),
                Column("estado", "Estado", align="center", width=130, badge=badge_estado),
            ],
            empty_text="Aún no hay categorías. Escribe un nombre arriba y pulsa \"Agregar categoría\".",
            min_height=320,
        )
        self.tabla.selection_changed.connect(self._al_seleccionar)
        self.tabla.row_activated.connect(lambda _: self._editar())
        listado.body.addWidget(self.tabla, 1)
        self.content.addWidget(listado, 1)
        self._al_seleccionar(None)

    def refresh(self, seleccionar_id=None):
        self.tabla.set_rows(controlador_categorias.obtener_lista_categorias())
        self.tabla.set_filter_text(self.buscador.text())
        if seleccionar_id is not None:
            self.tabla.select_by("id_categoria", seleccionar_id)

    def _al_seleccionar(self, fila):
        hay = fila is not None
        self.boton_editar.setEnabled(hay)
        # Eliminar solo tiene sentido si ningun producto usa la categoria.
        # (El modelo vuelve a comprobarlo al borrar.)
        libre = hay and not fila["total_productos"]
        self.boton_eliminar.setEnabled(libre)
        if not hay:
            self.boton_eliminar.setToolTip("Selecciona una categoría de la tabla")
        elif libre:
            self.boton_eliminar.setToolTip("Eliminar la categoría seleccionada")
        else:
            self.boton_eliminar.setToolTip(
                "No se puede eliminar: tiene productos registrados.")

    def _editar(self):
        fila = self.tabla.selected_row()
        if fila is None:
            messages.warning(self, "Selecciona una categoría",
                             "Haz clic en una categoría de la tabla y luego pulsa Editar.")
            return
        datos = controlador_categorias.obtener_categoria_por_id(fila["id_categoria"])
        if datos is None:
            self.refresh()
            return
        if CategoriaDialog(self, datos).exec():
            self.refresh(seleccionar_id=fila["id_categoria"])

    def _eliminar(self):
        fila = self.tabla.selected_row()
        if fila is None:
            return
        datos = controlador_categorias.obtener_categoria_por_id(fila["id_categoria"])
        if datos is None:
            self.refresh()
            return
        if datos["total_productos"]:
            messages.warning(
                self, "No se puede eliminar",
                f"\"{datos['nombre']}\" tiene {datos['total_productos']} producto(s) registrado(s). "
                "Cambia esos productos a otra categoría y vuelve a intentarlo.")
            self.refresh(seleccionar_id=datos["id_categoria"])
            return
        if not messages.confirm(
                self, "¿Eliminar categoría?",
                f"Se eliminará \"{datos['nombre']}\" de forma permanente. "
                "Esta acción no se puede deshacer.",
                confirmar="Eliminar", danger=True):
            return
        exito, mensaje = controlador_categorias.eliminar_categoria(datos["id_categoria"])
        if exito:
            messages.success(self, mensaje)
            self.refresh()
        else:
            messages.error(self, "No se pudo eliminar", mensaje)
            self.refresh(seleccionar_id=datos["id_categoria"])

    def _registrar(self):
        nombre = self.entrada_nombre.text()
        self.campo_nombre.set_invalid(False)
        self.error.hide()
        if not nombre.strip():
            self.campo_nombre.set_invalid(True)
            self.error.setText("Escribe el nombre de la categoría.")
            self.error.show()
            self.entrada_nombre.setFocus()
            return

        exito, mensaje = controlador_categorias.registrar_categoria(nombre)
        if exito:
            messages.success(self, mensaje)
            self.entrada_nombre.clear()
            self.refresh()
            self.tabla.select_by("nombre", " ".join(nombre.split()))
        else:
            self.campo_nombre.set_invalid(True)
            self.error.setText(mensaje)
            self.error.show()
