"""
Barra superior: marca, fecha, usuario, codigo de recuperacion y cerrar sesion.

El administrador cambia contrasenas y genera su codigo desde la seccion
Seguridad; la cuenta de ventas no tiene esa seccion, asi que conserva
aqui el boton "Recuperacion".
"""

from datetime import date

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from ui.icons import logo_pixmap
from ui.widgets.common import button, label

_NOMBRE_ROL = {"admin": "Administrador", "vendedor": "Ventas"}

_DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
          "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def fecha_larga(d=None):
    d = d or date.today()
    return f"{_DIAS[d.weekday()].capitalize()} {d.day} de {_MESES[d.month - 1]} de {d.year}"


class TopBar(QFrame):
    logout_requested = Signal()
    recovery_code_requested = Signal()

    def __init__(self, usuario, parent=None):
        super().__init__(parent)
        self.setObjectName("TopBar")
        self.setFixedHeight(68)

        fila = QHBoxLayout(self)
        fila.setContentsMargins(22, 0, 18, 0)
        fila.setSpacing(12)

        logo = QLabel()
        logo.setPixmap(logo_pixmap(30))
        marca = QLabel("Tienda Jazmín")
        marca.setObjectName("BrandName")
        fila.addWidget(logo)
        fila.addWidget(marca)
        fila.addStretch(1)

        self.fecha = label(fecha_larga(), "muted")
        fila.addWidget(self.fecha)
        fila.addSpacing(18)

        nombre = (usuario or {}).get("nombre") or "Usuario"
        rol = (usuario or {}).get("rol") or ""
        iniciales = "".join(p[0] for p in nombre.split()[:2]).upper() or "U"

        avatar = QLabel(iniciales)
        avatar.setObjectName("Avatar")
        avatar.setFixedSize(36, 36)
        avatar.setAlignment(Qt.AlignCenter)
        fila.addWidget(avatar)

        textos = QVBoxLayout()
        textos.setSpacing(0)
        etiqueta_nombre = QLabel(nombre)
        etiqueta_nombre.setObjectName("UserName")
        etiqueta_rol = QLabel(_NOMBRE_ROL.get(rol, rol.capitalize()))
        etiqueta_rol.setObjectName("UserRole")
        textos.addWidget(etiqueta_nombre)
        textos.addWidget(etiqueta_rol)
        fila.addLayout(textos)
        fila.addSpacing(10)

        if rol != "admin":
            fila.addWidget(button("Recuperación", "key", variant="ghost",
                                  tooltip="Generar un nuevo código de recuperación de contraseña",
                                  on_click=lambda: self.recovery_code_requested.emit()))

        salir = button("Cerrar sesión", "logout", variant="ghost",
                       on_click=lambda: self.logout_requested.emit())
        fila.addWidget(salir)

    def refresh_date(self):
        self.fecha.setText(fecha_larga())
