"""
Ventana principal: barra superior + menu lateral + contenido.

Las pantallas viven en un QStackedWidget: cambiar de seccion no abre
ventanas nuevas. Cada vez que se entra a una seccion se llama a su
refresh(), asi los datos siempre estan actualizados.

Solo se construyen las secciones que permite el rol del usuario
(ver helpers/permisos.py): el administrador ve todas las secciones y
el usuario de ventas ve reportes, ventas, creditos y clientes.

Atajos: Ctrl+1 ... Ctrl+N para cambiar de seccion, F5 para recargar.
"""

import traceback

from PySide6.QtCore import Signal
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QMainWindow, QStackedWidget, QVBoxLayout, QWidget

from controllers import controlador_login
from helpers import permisos, sesion
from ui.dialogs.password_dialog import PasswordDialog
from ui.dialogs.recuperacion_dialog import CodigoRecuperacionDialog, NuevoCodigoDialog
from ui.pages.categorias import CategoriasPage
from ui.pages.clientes import ClientesPage
from ui.pages.creditos import CreditosPage
from ui.pages.dashboard import DashboardPage
from ui.pages.inventario import InventarioPage
from ui.pages.productos import ProductosPage
from ui.pages.reportes import ReportesPage
from ui.pages.seguridad import SeguridadPage
from ui.pages.ventas import VentasPage
from ui.widgets import messages
from ui.widgets.messages import Toast
from ui.widgets.sidebar import Sidebar
from ui.widgets.topbar import TopBar

# (clave, texto del menu, icono, clase de la pantalla), agrupadas.
SECCIONES = [
    [("inicio", "Inicio", "home", DashboardPage),
     ("reportes", "Reportes", "chart", ReportesPage)],
    [("ventas", "Ventas", "cart", VentasPage),
     ("creditos", "Créditos", "wallet", CreditosPage),
     ("clientes", "Clientes", "users", ClientesPage)],
    [("inventario", "Inventario", "swap", InventarioPage),
     ("productos", "Productos", "box", ProductosPage),
     ("categorias", "Categorías", "tag", CategoriasPage)],
    [("seguridad", "Seguridad", "shield", SeguridadPage)],
]


class MainWindow(QMainWindow):
    closed = Signal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Tienda Jazmín - Sistema de gestión")
        self.setMinimumSize(980, 620)
        self.logout_requested = False

        raiz = QWidget()
        raiz.setObjectName("AppRoot")
        self.setCentralWidget(raiz)
        vertical = QVBoxLayout(raiz)
        vertical.setContentsMargins(0, 0, 0, 0)
        vertical.setSpacing(0)

        self.topbar = TopBar(sesion.obtener_usuario_actual())
        self.topbar.logout_requested.connect(self._cerrar_sesion)
        vertical.addWidget(self.topbar)

        cuerpo = QHBoxLayout()
        cuerpo.setContentsMargins(0, 0, 0, 0)
        cuerpo.setSpacing(0)
        vertical.addLayout(cuerpo, 1)

        permitidas = permisos.secciones_permitidas()
        secciones = [[s for s in grupo if s[0] in permitidas] for grupo in SECCIONES]
        secciones = [grupo for grupo in secciones if grupo]

        grupos_menu = [[(clave, texto, ico) for clave, texto, ico, _ in grupo] for grupo in secciones]
        self.sidebar = Sidebar(grupos_menu)
        self.sidebar.page_selected.connect(self.navigate)
        cuerpo.addWidget(self.sidebar)

        self.stack = QStackedWidget()
        cuerpo.addWidget(self.stack, 1)

        self.pages = {}
        numero = 1
        for grupo in secciones:
            for clave, texto, _ico, clase in grupo:
                pagina = clase(self.navigate)
                self.pages[clave] = pagina
                self.stack.addWidget(pagina)
                atajo = f"Ctrl+{numero}"
                QShortcut(QKeySequence(atajo), self, activated=lambda c=clave: self.navigate(c))
                self.sidebar.set_shortcut_hint(clave, atajo)
                numero += 1

        QShortcut(QKeySequence("F5"), self, activated=self._recargar_actual)

        self.toast = Toast(raiz)
        self._clave_actual = None
        inicial = permisos.seccion_inicial()
        if inicial in self.pages:
            self.navigate(inicial)
        elif secciones:
            self.navigate(secciones[0][0][0])
        self._ajustar_tamano()

    # --- Navegacion ---

    def navigate(self, clave, accion=None):
        pagina = self.pages.get(clave)
        if pagina is None:
            return
        self._clave_actual = clave
        self.sidebar.set_current(clave)
        self.stack.setCurrentWidget(pagina)
        pagina.scroll.verticalScrollBar().setValue(0)
        self.topbar.refresh_date()
        self._refrescar(pagina)
        if accion and hasattr(pagina, "run_action"):
            pagina.run_action(accion)

    def _refrescar(self, pagina):
        try:
            pagina.refresh()
        except Exception as error:  # la base de datos no respondio, etc.
            traceback.print_exc()
            messages.error(self, "No se pudieron cargar los datos",
                           f"Ocurrió un problema al leer la base de datos:\n{error}")

    def _recargar_actual(self):
        if self._clave_actual:
            self._refrescar(self.pages[self._clave_actual])
            self.show_toast("Datos actualizados.")

    # --- Avisos ---

    def show_toast(self, texto):
        self.toast.show_message(texto)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        if self.toast.isVisible():
            self.toast.reposition()

    # --- Sesion / ventana ---

    # Las usa la seccion Seguridad (solo administrador). Devuelven True si
    # se completo la accion.

    def cambiar_password(self):
        if not permisos.es_admin():
            return False
        dialogo = PasswordDialog(self)
        if dialogo.exec():
            self.show_toast(dialogo.mensaje_exito)
            return True
        return False

    def nuevo_codigo_recuperacion(self):
        if not permisos.es_admin():
            return False
        dialogo = NuevoCodigoDialog(self)
        if dialogo.exec():
            CodigoRecuperacionDialog(
                self, dialogo.codigo,
                "Tu código anterior ya no sirve. Guarda este nuevo en un lugar seguro.",
            ).exec()
            self.show_toast("Se generó un nuevo código de recuperación.")
            return True
        return False

    def _cerrar_sesion(self):
        if messages.confirm(self, "¿Cerrar sesión?",
                            "Volverás a la pantalla de inicio de sesión.",
                            confirmar="Cerrar sesión"):
            self.logout_requested = True
            self.close()

    def closeEvent(self, evento):
        # Cubre "Cerrar sesión" y cerrar con la X: ambos quedan en el historial.
        if sesion.hay_sesion_activa():
            try:
                controlador_login.cerrar_sesion()
            except Exception:
                traceback.print_exc()
                sesion.cerrar_sesion()
        super().closeEvent(evento)
        self.closed.emit()

    def _ajustar_tamano(self):
        pantalla = QGuiApplication.primaryScreen()
        if pantalla is None:
            self.resize(1280, 800)
            return
        area = pantalla.availableGeometry()
        self._maximizar = area.width() <= 1440 or area.height() <= 860
        ancho = min(1440, area.width() - 80)
        alto = min(900, area.height() - 60)
        self.resize(ancho, alto)
        self.move(area.center().x() - ancho // 2, area.center().y() - alto // 2)

    def mostrar(self):
        if getattr(self, "_maximizar", False):
            self.showMaximized()
        else:
            self.show()
