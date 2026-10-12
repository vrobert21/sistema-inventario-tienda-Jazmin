"""
Recuperacion de contrasena sin internet ni correo.

Cada usuario tiene un codigo de recuperacion de un solo uso:

- CodigoRecuperacionDialog: muestra el codigo (una sola vez) para que
  el usuario lo anote o lo guarde en un lugar seguro.
- RecuperarPasswordDialog: desde la pantalla de inicio de sesion, con
  usuario + codigo se elige una contrasena nueva. Al terminar se genera
  y muestra un codigo nuevo (el usado ya no sirve).
- NuevoCodigoDialog: con la sesion iniciada, genera un codigo nuevo
  confirmando la contrasena (por si el anterior se perdio).

La validacion vive en controlador_login.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QLabel, QLineEdit

from controllers import controlador_login
from ui import theme
from ui.widgets.common import button, label
from ui.widgets.form_dialog import FormDialog
from ui.widgets.forms import FormField, text_input


def _password_input(placeholder):
    campo = QLineEdit()
    campo.setPlaceholderText(placeholder)
    campo.setEchoMode(QLineEdit.Password)
    campo.setMaxLength(128)
    return campo


class CodigoRecuperacionDialog(FormDialog):
    def __init__(self, parent, codigo, motivo=""):
        super().__init__(
            parent,
            "Tu código de recuperación",
            motivo or "Si olvidas tu contraseña, con este código podrás crear una nueva.",
            icon_name="key",
            texto_guardar="Ya lo guardé",
            ancho=560,
        )
        self.cancel_button.hide()
        self._codigo = codigo

        etiqueta = QLabel(codigo)
        etiqueta.setAlignment(Qt.AlignCenter)
        etiqueta.setTextInteractionFlags(Qt.TextSelectableByMouse)
        etiqueta.setStyleSheet(
            f"font-family: Consolas, 'Courier New', monospace; font-size: 28px; font-weight: 600;"
            f"letter-spacing: 3px; color: {theme.PRIMARY}; background: {theme.PRIMARY_SOFT};"
            f"border-radius: 10px; padding: 18px;"
        )
        self.form.addWidget(etiqueta, 0, 0, 1, 2)

        self.boton_copiar = button("Copiar código", "copy", variant="secondary", on_click=self._copiar)
        self.boton_copiar.setAutoDefault(False)
        self.form.addWidget(self.boton_copiar, 1, 0, 1, 2, Qt.AlignCenter)

        aviso = label(
            "Anótalo en papel o guárdalo en un lugar seguro: no se volverá a mostrar. "
            "Cada código sirve una sola vez; al usarlo se te dará uno nuevo.",
            "caption", wrap=True,
        )
        aviso.setStyleSheet(f"color: {theme.WARNING};")
        self.form.addWidget(aviso, 2, 0, 1, 2)

    def _copiar(self):
        QGuiApplication.clipboard().setText(self._codigo)
        self.boton_copiar.setText("Copiado")


class RecuperarPasswordDialog(FormDialog):
    def __init__(self, parent, usuario_inicial=""):
        super().__init__(
            parent,
            "Recuperar contraseña",
            "Escribe tu usuario, tu código de recuperación y la nueva contraseña.",
            icon_name="key",
            texto_guardar="Guardar contraseña",
            ancho=560,
        )
        self.codigo_nuevo = None
        self.mensaje_exito = ""

        self.campo_usuario = self.add_field(
            FormField("Usuario", text_input("Tu usuario", 80), requerido=True), 0, 0, 2)
        self.campo_usuario.control.setText(usuario_inicial.strip())

        entrada_codigo = text_input("Ej. K7QM-3XRA-9TPW", 20)
        self.campo_codigo = self.add_field(
            FormField("Código de recuperación", entrada_codigo, requerido=True,
                      ayuda="El código que se te mostró al iniciar sesión por primera vez. "
                            "Si eres de ventas y no lo tienes, pide al administrador "
                            "que cambie tu contraseña."),
            1, 0, 2)
        self.campo_nueva = self.add_field(
            FormField("Nueva contraseña", _password_input("Mínimo 6 caracteres"),
                      requerido=True), 2, 0)
        self.campo_confirmacion = self.add_field(
            FormField("Confirmar nueva contraseña", _password_input("Repite la nueva contraseña"),
                      requerido=True), 2, 1)

        if usuario_inicial.strip():
            entrada_codigo.setFocus()
        else:
            self.campo_usuario.control.setFocus()

    def save(self):
        exito, mensaje, campo, codigo = controlador_login.recuperar_password(
            self.campo_usuario.control.text(),
            self.campo_codigo.control.text(),
            self.campo_nueva.control.text(),
            self.campo_confirmacion.control.text(),
        )
        if not exito:
            campos = {"usuario": self.campo_usuario, "codigo": self.campo_codigo,
                      "nueva": self.campo_nueva, "confirmacion": self.campo_confirmacion}
            self.show_error(mensaje, campos.get(campo))
            return False

        self.mensaje_exito = mensaje
        self.codigo_nuevo = codigo
        return True


class NuevoCodigoDialog(FormDialog):
    def __init__(self, parent):
        super().__init__(
            parent,
            "Nuevo código de recuperación",
            "Se generará un código nuevo y el anterior dejará de funcionar.",
            icon_name="key",
            texto_guardar="Generar código",
            ancho=520,
        )
        self.codigo = None
        self.campo_password = self.add_field(
            FormField("Tu contraseña actual", _password_input("Confirma tu contraseña"),
                      requerido=True), 0, 0, 2)
        self.campo_password.control.setFocus()

    def save(self):
        exito, mensaje, codigo = controlador_login.regenerar_codigo_recuperacion(
            self.campo_password.control.text()
        )
        if not exito:
            self.show_error(mensaje, self.campo_password)
            return False
        self.codigo = codigo
        return True
