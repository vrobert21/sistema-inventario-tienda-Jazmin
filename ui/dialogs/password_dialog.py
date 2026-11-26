"""
Formulario para cambiar contrasenas.

Cualquier usuario puede cambiar la suya propia confirmando con su
contrasena actual (exigido por ley: cada rol debe poder cambiar su
propia contrasena). El administrador, ademas, puede elegir una cuenta
de ventas en vez de la suya. La validacion vive en
controlador_usuarios.cambiar_password.
"""

from PySide6.QtWidgets import QLineEdit

from controllers import controlador_usuarios
from ui.widgets.form_dialog import FormDialog
from ui.widgets.forms import FormField, choice_combo


def _password_input(placeholder):
    campo = QLineEdit()
    campo.setPlaceholderText(placeholder)
    campo.setEchoMode(QLineEdit.Password)
    campo.setMaxLength(128)
    return campo


class PasswordDialog(FormDialog):
    def __init__(self, parent):
        cuentas = controlador_usuarios.listar_cuentas_editables()
        # Si solo hay una cuenta disponible (cualquier cuenta de ventas,
        # o el administrador sin cuentas de ventas creadas), no tiene
        # sentido mostrar un selector con una sola opcion.
        self._id_unico = cuentas[0][1] if len(cuentas) == 1 else None

        super().__init__(
            parent,
            "Cambiar contraseña",
            "Confirma con tu contraseña actual." if self._id_unico is not None
            else "Elige la cuenta y confirma con tu contraseña actual.",
            icon_name="lock",
            texto_guardar="Cambiar contraseña",
            ancho=560,
        )
        self.mensaje_exito = ""

        fila = 0
        self.campo_cuenta = None
        if self._id_unico is None:
            self.campo_cuenta = self.add_field(
                FormField("Cuenta", choice_combo(cuentas), requerido=True), fila, 0, 2)
            fila += 1
        self.campo_actual = self.add_field(
            FormField("Tu contraseña actual", _password_input("Tu contraseña actual"),
                      requerido=True), fila, 0, 2)
        fila += 1
        self.campo_nueva = self.add_field(
            FormField("Nueva contraseña", _password_input("Mínimo 6 caracteres"),
                      requerido=True), fila, 0)
        self.campo_confirmacion = self.add_field(
            FormField("Confirmar nueva contraseña", _password_input("Repite la nueva contraseña"),
                      requerido=True), fila, 1)

        self.campo_actual.control.setFocus()

    def save(self):
        id_cuenta = (self._id_unico if self.campo_cuenta is None
                     else self.campo_cuenta.control.currentData())
        exito, mensaje, campo = controlador_usuarios.cambiar_password(
            id_cuenta,
            self.campo_actual.control.text(),
            self.campo_nueva.control.text(),
            self.campo_confirmacion.control.text(),
        )
        if not exito:
            campos = {"actual": self.campo_actual, "nueva": self.campo_nueva,
                      "confirmacion": self.campo_confirmacion}
            self.show_error(mensaje, campos.get(campo))
            return False

        self.mensaje_exito = mensaje
        return True
