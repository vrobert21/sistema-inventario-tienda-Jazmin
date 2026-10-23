"""
Ventana de inicio de sesion.

Usa controlador_login.iniciar_sesion(usuario, password), igual que
la version anterior; si es correcto, el controlador guarda la sesion
en helpers/sesion.py y esta ventana se cierra con accept().

Si el usuario aun no tiene codigo de recuperacion, se le muestra uno
antes de entrar. "¿Olvidaste tu contraseña?" abre la recuperacion.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QFrame, QLabel, QLineEdit, QVBoxLayout

from controllers import controlador_login
from ui import theme
from ui.dialogs.recuperacion_dialog import CodigoRecuperacionDialog, RecuperarPasswordDialog
from ui.icons import icon, logo_pixmap
from ui.widgets.common import button, label
from ui.widgets.forms import FormField


class LoginWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("LoginBackdrop")
        self.setWindowTitle("Iniciar sesión - Tienda Jazmín")
        self.setWindowFlag(Qt.WindowContextHelpButtonHint, False)
        self.setMinimumSize(520, 600)
        self.resize(960, 680)

        fondo = QVBoxLayout(self)
        fondo.setContentsMargins(24, 24, 24, 24)
        fondo.addStretch(1)

        tarjeta = QFrame()
        tarjeta.setObjectName("LoginCard")
        tarjeta.setFixedWidth(420)
        caja = QVBoxLayout(tarjeta)
        caja.setContentsMargins(36, 36, 36, 32)
        caja.setSpacing(18)

        logo = QLabel()
        logo.setPixmap(logo_pixmap(48))
        caja.addWidget(logo, 0, Qt.AlignLeft)

        titulos = QVBoxLayout()
        titulos.setSpacing(4)
        titulo = QLabel("Tienda Jazmín")
        titulo.setObjectName("LoginTitle")
        titulos.addWidget(titulo)
        titulos.addWidget(label("Inicia sesión para continuar.", "subtitle"))
        caja.addLayout(titulos)
        caja.addSpacing(4)

        self.entrada_usuario = QLineEdit()
        self.entrada_usuario.setPlaceholderText("Tu usuario")
        self.entrada_usuario.addAction(icon("user", theme.TEXT_SUBTLE, 18), QLineEdit.LeadingPosition)
        self.campo_usuario = FormField("Usuario", self.entrada_usuario)
        caja.addWidget(self.campo_usuario)

        self.entrada_password = QLineEdit()
        self.entrada_password.setPlaceholderText("Tu contraseña")
        self.entrada_password.setEchoMode(QLineEdit.Password)
        self.entrada_password.addAction(icon("lock", theme.TEXT_SUBTLE, 18), QLineEdit.LeadingPosition)
        self._accion_ver = self.entrada_password.addAction(icon("eye", theme.TEXT_MUTED, 18),
                                                           QLineEdit.TrailingPosition)
        self._accion_ver.setToolTip("Mostrar contraseña")
        self._accion_ver.triggered.connect(self._alternar_password)
        self.campo_password = FormField("Contraseña", self.entrada_password)
        caja.addWidget(self.campo_password)

        self.error = QLabel()
        self.error.setObjectName("ErrorBanner")
        self.error.setWordWrap(True)
        self.error.hide()
        caja.addWidget(self.error)

        # Ayuda para cuentas de ventas: no tienen codigo de recuperacion.
        self.ayuda_olvido = label("Si olvidó su contraseña, contacte al administrador.",
                                  "caption", wrap=True)
        self.ayuda_olvido.hide()
        caja.addWidget(self.ayuda_olvido)

        self.boton_entrar = button("Iniciar sesión", variant="primary", large=True,
                                   on_click=self._iniciar_sesion)
        # Enter se maneja con returnPressed; sin boton por defecto para no
        # ejecutar el inicio de sesion dos veces.
        self.boton_entrar.setAutoDefault(False)
        self.boton_entrar.setDefault(False)
        caja.addWidget(self.boton_entrar)

        self.boton_olvido = button("¿Olvidaste tu contraseña?", "key", variant="ghost",
                                   on_click=self._recuperar_password)
        self.boton_olvido.setAutoDefault(False)
        # Solo se muestra para el administrador (ver _evaluar_usuario).
        self.boton_olvido.hide()
        caja.addWidget(self.boton_olvido, 0, Qt.AlignHCenter)

        fondo.addWidget(tarjeta, 0, Qt.AlignHCenter)
        fondo.addStretch(1)

        self.entrada_usuario.returnPressed.connect(self.entrada_password.setFocus)
        self.entrada_password.returnPressed.connect(self._iniciar_sesion)
        self.entrada_usuario.editingFinished.connect(self._evaluar_usuario)
        self.entrada_usuario.textChanged.connect(self._ocultar_ayuda_olvido)
        self.entrada_usuario.setFocus()

    def _ocultar_ayuda_olvido(self):
        self.boton_olvido.hide()
        self.ayuda_olvido.hide()

    def _evaluar_usuario(self):
        # Al terminar de escribir el usuario: el enlace solo para el admin.
        self.boton_olvido.setVisible(controlador_login.es_admin(self.entrada_usuario.text()))

    def _alternar_password(self):
        visible = self.entrada_password.echoMode() == QLineEdit.Normal
        self.entrada_password.setEchoMode(QLineEdit.Password if visible else QLineEdit.Normal)
        self._accion_ver.setIcon(icon("eye" if visible else "eye-off", theme.TEXT_MUTED, 18))
        self._accion_ver.setToolTip("Mostrar contraseña" if visible else "Ocultar contraseña")

    def _iniciar_sesion(self):
        self.campo_usuario.set_invalid(False)
        self.campo_password.set_invalid(False)

        exito, mensaje = controlador_login.iniciar_sesion(
            self.entrada_usuario.text(), self.entrada_password.text()
        )
        if exito:
            codigo = controlador_login.asegurar_codigo_recuperacion()
            if codigo:
                CodigoRecuperacionDialog(
                    self, codigo,
                    "Guarda este código: si algún día olvidas tu contraseña, "
                    "lo necesitarás para crear una nueva.",
                ).exec()
            self.accept()
            return

        self.error.setText(mensaje)
        self.error.show()
        # Si el usuario no existe solo queda el error generico.
        nombre = self.entrada_usuario.text()
        self.boton_olvido.setVisible(controlador_login.es_admin(nombre))
        self.ayuda_olvido.setVisible(controlador_login.es_vendedor(nombre))
        self.entrada_password.clear()
        if not self.entrada_usuario.text().strip():
            self.campo_usuario.set_invalid(True)
            self.entrada_usuario.setFocus()
        else:
            self.campo_password.set_invalid(True)
            self.entrada_password.setFocus()

    def _recuperar_password(self):
        # El enlace oculto es solo presentacion; recuperar_password()
        # vuelve a validar en el controlador que la cuenta sea admin.
        if not controlador_login.es_admin(self.entrada_usuario.text()):
            self._ocultar_ayuda_olvido()
            return
        self.error.hide()
        dialogo = RecuperarPasswordDialog(self, self.entrada_usuario.text())
        if not dialogo.exec():
            return
        CodigoRecuperacionDialog(
            self, dialogo.codigo_nuevo,
            f"{dialogo.mensaje_exito} Tu código anterior ya no sirve; guarda este nuevo.",
        ).exec()
        self.entrada_usuario.setText(dialogo.campo_usuario.control.text().strip())
        self.entrada_password.clear()
        self.campo_password.set_invalid(False)
        self.entrada_password.setFocus()
