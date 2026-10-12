"""
Iconos de la interfaz.

Set propio de iconos de linea (24x24, mismo grosor de trazo), guardado
como SVG en texto y dibujado con QtSvg, que ya viene incluido en
PySide6. Asi no se depende de fuentes de iconos externas ni de
archivos de imagen sueltos.

Uso:
    from ui.icons import icon
    boton.setIcon(icon("plus", color="#ffffff"))
"""

from functools import lru_cache

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from ui import theme

# Solo el contenido interno de cada SVG. El contenedor (viewBox,
# grosor y color de trazo) se agrega en _svg().
_PATHS = {
    "home": '<path d="M3 11 12 4l9 7"/><path d="M5 9.5V20h14V9.5"/><path d="M10 20v-5.5h4V20"/>',
    "box": '<path d="M3 7.5 12 3l9 4.5v9L12 21l-9-4.5z"/><path d="M3 7.5 12 12l9-4.5"/><path d="M12 12v9"/>',
    "tag": '<path d="M3.5 12.5V4h8.5l9 9-8.5 8.5z"/><circle cx="8" cy="8.5" r="1.4"/>',
    "swap": '<path d="M7 4v15"/><path d="M3 8l4-4 4 4"/><path d="M17 20V5"/><path d="M21 16l-4 4-4-4"/>',
    "users": '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20c.8-3.5 3.3-5.5 6.5-5.5s5.7 2 6.5 5.5"/>'
             '<path d="M15.5 4.8a3 3 0 0 1 0 6"/><path d="M17.5 14.8c2 .6 3.4 2.3 4 5.2"/>',
    "cart": '<path d="M2.5 4h2.8l2.3 11h10.9l2-8H6.3"/><circle cx="9.5" cy="19.5" r="1.3"/><circle cx="17" cy="19.5" r="1.3"/>',
    "wallet": '<rect x="3" y="6.5" width="18" height="13.5" rx="2.5"/><path d="M16 13.2h2.2"/><path d="M5.5 6.5 15.5 3.5l1 3"/>',
    "logout": '<path d="M14.5 4H18a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3.5"/><path d="M9.5 16l-4-4 4-4"/><path d="M5.5 12H15"/>',
    "plus": '<path d="M12 5v14"/><path d="M5 12h14"/>',
    "edit": '<path d="M4 20h4L19 9l-4-4L4 16z"/><path d="M13 7l4 4"/>',
    "power": '<path d="M12 3v8"/><path d="M6.3 6.8a8 8 0 1 0 11.4 0"/>',
    "search": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 20.5 20.5"/>',
    "alert": '<path d="M12 4 2.8 19.5h18.4z"/><path d="M12 10v4.5"/><path d="M12 17.3v.2"/>',
    "dollar": '<path d="M12 3v18"/><path d="M16.5 7.5c-.8-1.5-2.5-2.3-4.5-2.3-2.6 0-4.3 1.3-4.3 3.2 '
              '0 4.3 9 2.3 9 6.8 0 2-1.9 3.3-4.6 3.3-2.1 0-3.9-.9-4.7-2.5"/>',
    "history": '<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5V12l3 2"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "x": '<path d="M6 6l12 12"/><path d="M18 6 6 18"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5.5"/><path d="M12 7.8v.2"/>',
    "user": '<circle cx="12" cy="8" r="4"/><path d="M4.5 20.5c1-4 3.9-6 7.5-6s6.5 2 7.5 6"/>',
    "lock": '<rect x="5" y="10.5" width="14" height="10" rx="2"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
    "eye": '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z"/><circle cx="12" cy="12" r="3"/>',
    "eye-off": '<path d="M4 4l16 16"/><path d="M9.9 5.8A9.6 9.6 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a16 16 0 0 1-2.6 3.4"/>'
               '<path d="M6.6 7.4C4 9.1 2.5 12 2.5 12S6 18.5 12 18.5a9 9 0 0 0 4.3-1.1"/><path d="M10 10.2a3 3 0 0 0 4 4"/>',
    "arrow-in": '<path d="M12 4v11"/><path d="M7.5 10.5 12 15l4.5-4.5"/><path d="M4 20h16"/>',
    "arrow-out": '<path d="M12 15V4"/><path d="M7.5 8.5 12 4l4.5 4.5"/><path d="M4 20h16"/>',
    "trash": '<path d="M4 7h16"/><path d="M9.5 7V4.5h5V7"/><path d="M6 7l1 13h10l1-13"/>',
    "refresh": '<path d="M20 12a8 8 0 1 1-2.3-5.7"/><path d="M20 4v5h-5"/>',
    "chevron-down": '<path d="M6 9.5l6 6 6-6"/>',
    "chevron-up": '<path d="M6 14.5l6-6 6 6"/>',
    "chart": '<path d="M4 20V4"/><path d="M4 20h16"/><rect x="7.5" y="11" width="3" height="6" rx=".6"/>'
             '<rect x="12.5" y="7" width="3" height="10" rx=".6"/><rect x="17.5" y="13" width="3" height="4" rx=".6"/>',
    "file": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/>'
            '<path d="M9 13h6"/><path d="M9 17h4"/>',
    "calendar": '<rect x="3.5" y="5" width="17" height="15.5" rx="2.5"/><path d="M3.5 10h17"/><path d="M8 3v4"/><path d="M16 3v4"/>',
    "chevron-left": '<path d="M14.5 6l-6 6 6 6"/>',
    "chevron-right": '<path d="M9.5 6l6 6-6 6"/>',
    "key": '<circle cx="8" cy="15" r="4.5"/><path d="M11.2 11.8 20 3"/><path d="M16.5 6.5l3 3"/><path d="M14 9l2 2"/>',
    "shield": '<path d="M12 3 4.5 6v5.5c0 4.6 3.2 8 7.5 9.5 4.3-1.5 7.5-4.9 7.5-9.5V6z"/><path d="M8.8 12.2l2.2 2.2 4.3-4.4"/>',
    "folder": '<path d="M3.5 7a2 2 0 0 1 2-2h4l2 2.5h7a2 2 0 0 1 2 2V18a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
    "copy": '<rect x="8.5" y="8.5" width="11.5" height="11.5" rx="2"/><path d="M15.5 8.5V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7.5a2 2 0 0 0 2 2h2.5"/>',
    "database": '<ellipse cx="12" cy="6" rx="7.5" ry="3"/><path d="M4.5 6v12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3V6"/><path d="M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3"/>',
    "receipt": '<path d="M6 3h12v18l-3-2-3 2-3-2-3 2z"/><path d="M9 8h6"/><path d="M9 12h6"/>',
}

# Marca de la tienda: una flor de cinco petalos (jazmin), rellena.
_LOGO = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
    '<g fill="{color}" transform="translate(12 12)">'
    + "".join(
        f'<ellipse cx="0" cy="-5.6" rx="3.3" ry="5.2" transform="rotate({a})" opacity="0.92"/>'
        for a in (0, 72, 144, 216, 288)
    )
    + '<circle r="2.4" fill="#ffffff"/></g></svg>'
)


def _svg(name, color, stroke=1.8):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{color}" stroke-width="{stroke}" stroke-linecap="round" stroke-linejoin="round">'
        f"{_PATHS[name]}</svg>"
    )


def _render(svg_text, size, ratio=None):
    """Dibuja un SVG en un QPixmap nitido tambien en pantallas HiDPI."""
    from PySide6.QtGui import QGuiApplication

    if ratio is None:
        screen = QGuiApplication.primaryScreen()
        ratio = screen.devicePixelRatio() if screen else 1.0
    pixmap = QPixmap(int(size * ratio), int(size * ratio))
    pixmap.fill(Qt.transparent)
    renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size * ratio, size * ratio))
    painter.end()
    pixmap.setDevicePixelRatio(ratio)
    return pixmap


@lru_cache(maxsize=256)
def pixmap(name, color=theme.TEXT_MUTED, size=20):
    return _render(_svg(name, color), size)


@lru_cache(maxsize=256)
def icon(name, color=theme.TEXT_MUTED, size=20, checked_color=None):
    """
    Devuelve un QIcon. Si se pasa checked_color, el icono cambia de
    color cuando el boton esta marcado (lo usa el menu lateral para
    resaltar la opcion activa).
    """
    qicon = QIcon()
    qicon.addPixmap(pixmap(name, color, size), QIcon.Normal, QIcon.Off)
    qicon.addPixmap(pixmap(name, theme.TEXT_SUBTLE, size), QIcon.Disabled, QIcon.Off)
    if checked_color:
        qicon.addPixmap(pixmap(name, checked_color, size), QIcon.Normal, QIcon.On)
    return qicon


@lru_cache(maxsize=8)
def logo_pixmap(size=32, color=theme.PRIMARY):
    return _render(_LOGO.format(color=color), size)


def save_png(name, color, size, path):
    """Guarda un icono como PNG (lo usa la hoja de estilos para flechas y checks)."""
    return _render(_svg(name, color, stroke=2.2), size, ratio=1.0).save(path, "PNG")
