"""
Piezas de formulario reutilizables.

- FormField: etiqueta + control + ayuda opcional, en vertical.
- SearchableCombo: lista desplegable en la que se puede escribir para
  buscar (util cuando hay muchos productos o clientes).
- money_input / int_input: campos numericos que solo aceptan valores validos.
- SearchField: caja de busqueda con icono de lupa.
"""

from PySide6.QtCore import QLocale, QRegularExpression, QSize, Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QComboBox, QCompleter, QDoubleSpinBox, QLabel, QLineEdit, QSpinBox,
    QVBoxLayout, QWidget,
)

from ui import theme
from ui.icons import icon
from ui.widgets.common import repolish

_LOCALE_C = QLocale.c()
_LOCALE_C.setNumberOptions(QLocale.NumberOption.OmitGroupSeparator)


class FormField(QWidget):
    def __init__(self, titulo, control, requerido=False, ayuda=None, parent=None):
        super().__init__(parent)
        self.control = control
        disposicion = QVBoxLayout(self)
        disposicion.setContentsMargins(0, 0, 0, 0)
        disposicion.setSpacing(6)

        texto = f"{titulo} <span style='color:{theme.DANGER}'>*</span>" if requerido else titulo
        self.label = QLabel(texto)
        self.label.setProperty("role", "fieldLabel")
        self.label.setTextFormat(Qt.RichText)
        self.label.setBuddy(control)
        disposicion.addWidget(self.label)
        disposicion.addWidget(control)

        self.help = None
        if ayuda:
            self.help = QLabel(ayuda)
            self.help.setProperty("role", "caption")
            self.help.setWordWrap(True)
            disposicion.addWidget(self.help)

    def set_invalid(self, invalido):
        self.control.setProperty("invalid", bool(invalido))
        repolish(self.control)


def text_input(placeholder="", max_length=None):
    campo = QLineEdit()
    campo.setPlaceholderText(placeholder)
    campo.setClearButtonEnabled(True)
    if max_length:
        campo.setMaxLength(max_length)
    return campo


def money_input(maximo=9_999_999.99):
    """Campo de dinero: siempre punto decimal y 2 decimales."""
    campo = QDoubleSpinBox()
    campo.setLocale(_LOCALE_C)
    campo.setDecimals(2)
    campo.setRange(0, maximo)
    campo.setPrefix("$ ")
    # Las flechas se ocultan desde el tema: con setButtonSymbols(NoButtons)
    # y la hoja de estilos, Qt deja el texto con 1 px de ancho (no se ve).
    campo.setProperty("sinFlechas", True)
    campo.lineEdit().setTextMargins(12, 0, 0, 0)  # el padding del tema no aplica aqui
    campo.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    campo.setAccelerated(True)
    return campo


def money_text_input(placeholder=""):
    """
    Dinero que puede quedar vacio (p. ej. limite de credito opcional).
    Solo acepta digitos y un punto con hasta 2 decimales, porque
    helpers.formato.texto_a_centavos trata la coma como separador de miles.
    """
    campo = text_input(placeholder)
    campo.setValidator(QRegularExpressionValidator(QRegularExpression(r"^\d{0,7}(\.\d{0,2})?$")))
    return campo


def int_input(minimo=0, maximo=1_000_000, con_flechas=True):
    campo = QSpinBox()
    campo.setLocale(_LOCALE_C)
    campo.setRange(minimo, maximo)
    campo.setAccelerated(True)
    campo.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
    if not con_flechas:
        campo.setProperty("sinFlechas", True)  # ver money_input
        campo.lineEdit().setTextMargins(12, 0, 0, 0)
    return campo


class SearchableCombo(QComboBox):
    """
    Lista desplegable con busqueda: se puede abrir con el mouse o
    escribir parte del nombre. current_data() devuelve el dato del
    elemento elegido, o None si el texto no coincide con ninguno.
    """

    def __init__(self, placeholder="Escribe para buscar...", parent=None):
        super().__init__(parent)
        self.setEditable(True)
        self.setInsertPolicy(QComboBox.NoInsert)
        self.setMaxVisibleItems(12)
        self.lineEdit().setPlaceholderText(placeholder)
        self.lineEdit().setClearButtonEnabled(True)
        completer = self.completer()
        completer.setFilterMode(Qt.MatchContains)
        completer.setCompletionMode(QCompleter.PopupCompletion)
        completer.setCaseSensitivity(Qt.CaseInsensitive)
        completer.popup().setStyleSheet("font-size: 15px;")

    def set_items(self, pares, mantener_seleccion=True):
        """pares: lista de (texto, dato)."""
        anterior = self.current_data() if mantener_seleccion else None
        self.blockSignals(True)
        self.clear()
        for texto, dato in pares:
            self.addItem(texto, dato)
        self.setCurrentIndex(-1)
        self.lineEdit().clear()
        self.blockSignals(False)
        if anterior is not None:
            self.select_data(anterior)
        else:
            self.currentIndexChanged.emit(-1)

    def current_data(self):
        texto = self.currentText().strip()
        if not texto:
            return None
        indice = self.findText(texto, Qt.MatchExactly)
        return self.itemData(indice) if indice >= 0 else None

    def select_data(self, dato):
        indice = self.findData(dato)
        self.setCurrentIndex(indice)
        if indice < 0:
            self.lineEdit().clear()


def choice_combo(pares):
    """Lista desplegable de solo seleccion. pares: lista de (texto, dato)."""
    combo = QComboBox()
    for texto, dato in pares:
        combo.addItem(texto, dato)
    combo.setCursor(Qt.PointingHandCursor)
    return combo


class SearchField(QLineEdit):
    def __init__(self, placeholder="Buscar...", parent=None):
        super().__init__(parent)
        self.setObjectName("SearchField")
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(True)
        self.addAction(icon("search", theme.TEXT_SUBTLE, 18), QLineEdit.LeadingPosition)
        self.setMinimumWidth(260)

    def sizeHint(self):
        return QSize(340, super().sizeHint().height())
