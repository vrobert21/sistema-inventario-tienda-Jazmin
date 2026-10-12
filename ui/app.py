"""
Arranque de la interfaz PySide6.

Flujo: inicio de sesion -> ventana principal -> (cerrar sesion) ->
inicio de sesion otra vez. Cerrar la ventana con la X termina el programa.
"""

import os
import sys
import traceback

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QApplication, QDialog

from ui.icons import logo_pixmap
from ui.styles import aplicar_tema


def _instalar_manejador_errores(app):
    """Muestra los errores inesperados en un dialogo en lugar de solo en la consola."""
    from ui.widgets import messages

    anterior = sys.excepthook

    def manejador(tipo, valor, tb):
        traceback.print_exception(tipo, valor, tb)
        try:
            messages.error(app.activeWindow(), "Ocurrió un error inesperado",
                           f"{valor}\n\nLa operación no se completó. Si se repite, revisa la consola.")
        except Exception:
            anterior(tipo, valor, tb)

    sys.excepthook = manejador


_RUTA_ICONO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tienda_jazmin.ico")


def _identificar_en_windows():
    """
    Hace que la barra de tareas de Windows muestre el icono de la tienda
    (y agrupe sus ventanas) en lugar del icono de Python.
    """
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("TiendaJazmin.Sistema")
        except Exception:
            pass


def _programar_respaldos(app):
    """
    El respaldo automatico se revisa al arrancar (main.py); este
    temporizador lo vuelve a revisar cada hora por si el programa
    se queda abierto varios dias seguidos.
    """
    from database.respaldo import respaldo_automatico_si_toca

    def revisar():
        try:
            respaldo_automatico_si_toca()
        except Exception:
            traceback.print_exc()

    temporizador = QTimer(app)
    temporizador.setInterval(60 * 60 * 1000)
    temporizador.timeout.connect(revisar)
    temporizador.start()


def run():
    _identificar_en_windows()
    # Escalado nitido en pantallas con 125% / 150% (comun en portatiles con Windows).
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("Tienda Jazmín")
    app.setQuitOnLastWindowClosed(False)
    app.styleHints().setColorScheme(Qt.ColorScheme.Light) #linea de cambio de tema.
    aplicar_tema(app)
    if os.path.exists(_RUTA_ICONO):
        app.setWindowIcon(QIcon(_RUTA_ICONO))
    else:
        app.setWindowIcon(logo_pixmap(64))
    _instalar_manejador_errores(app)
    _programar_respaldos(app)

    from ui.login_window import LoginWindow
    from ui.main_window import MainWindow

    while True:
        login = LoginWindow()
        if login.exec() != QDialog.Accepted:
            break

        ventana = MainWindow()
        ventana.closed.connect(app.quit)
        ventana.mostrar()
        app.exec()

        if not ventana.logout_requested:
            break
        ventana.deleteLater()

    return 0
