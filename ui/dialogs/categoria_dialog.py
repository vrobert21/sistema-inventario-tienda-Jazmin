"""
Formulario para editar el nombre de una categoria.

Usa controlador_categorias.modificar_categoria; el modelo valida que el
nombre no este vacio y que no lo tenga otra categoria.
"""

from controllers import controlador_categorias
from ui.widgets import messages
from ui.widgets.form_dialog import FormDialog
from ui.widgets.forms import FormField, text_input


class CategoriaDialog(FormDialog):
    def __init__(self, parent, categoria_existente):
        self.categoria = categoria_existente
        super().__init__(
            parent,
            "Editar categoría",
            "Cambiar el nombre no afecta a los productos que ya la usan.",
            icon_name="edit",
            texto_guardar="Guardar cambios",
            ancho=520,
        )
        self.campo_nombre = self.add_field(
            FormField("Nombre", text_input("Ej. Bebidas, Abarrotes, Limpieza", 80),
                      requerido=True), 0, 0, 2)
        self.campo_nombre.control.setText(self.categoria["nombre"])
        self.campo_nombre.control.selectAll()
        self.campo_nombre.control.returnPressed.connect(self._on_save)
        self.footer_note.setText("* Campo obligatorio")
        self.campo_nombre.control.setFocus()

    def save(self):
        nombre = self.campo_nombre.control.text()
        if not nombre.strip():
            self.show_error("Escribe el nombre de la categoría.", self.campo_nombre)
            return False

        exito, mensaje = controlador_categorias.modificar_categoria(
            self.categoria["id_categoria"], nombre)
        if not exito:
            self.show_error(mensaje, self.campo_nombre)
            return False

        messages.success(self.parentWidget(), mensaje)
        return True
