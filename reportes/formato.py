"""Formatos de presentacion usados en pantalla y en el PDF de reportes."""

from datetime import datetime


def dinero(centavos):
    """1234550 -> '$12,345.50'. Nunca devuelve 'None'."""
    return f"${(centavos or 0) / 100:,.2f}"


def entero(n):
    return f"{int(n or 0):,}"


def plural(n, singular, plural_):
    return f"{entero(n)} {singular if n == 1 else plural_}"


def fecha_hora(texto):
    """'2026-09-24 14:05:33' -> '24/09/2026 14:05'."""
    if not texto:
        return ""
    try:
        return datetime.strptime(str(texto)[:19], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return str(texto)


def fecha_hora_corta(texto):
    """'2026-09-24 14:05:33' -> '24/09/26 14:05' (para tablas angostas del PDF)."""
    if not texto:
        return ""
    try:
        return datetime.strptime(str(texto)[:19], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%y %H:%M")
    except ValueError:
        return str(texto)


def variacion(actual, anterior):
    """
    Texto de comparacion con el periodo anterior, o '' si no aplica.
    Ej.: '+15% vs. periodo anterior', 'sin cambios vs. periodo anterior'.
    """
    actual = actual or 0
    anterior = anterior or 0
    if anterior == 0:
        return "sin datos del período anterior" if actual == 0 else "sin ventas en el período anterior"
    cambio = (actual - anterior) / anterior * 100
    if abs(cambio) < 0.5:
        return "sin cambios vs. período anterior"
    return f"{cambio:+.0f}% vs. período anterior"


def lista_natural(elementos):
    """['a', 'b', 'c'] -> 'a, b y c'."""
    elementos = [e for e in elementos if e]
    if not elementos:
        return ""
    if len(elementos) == 1:
        return elementos[0]
    return ", ".join(elementos[:-1]) + " y " + elementos[-1]


ETIQUETA_PAGO = {"efectivo": "Efectivo", "tarjeta": "Tarjeta", "otro": "Otro", "credito": "Crédito"}
ORDEN_PAGO = ["efectivo", "tarjeta", "otro", "credito"]

ETIQUETA_OPERACION = {"venta": "Venta", "entrada": "Entrada", "salida": "Salida", "ajuste": "Ajuste"}

# Mismas etiquetas que ui/pages/seguridad.py (ahi ademas llevan un color de
# badge; aqui solo se necesita el texto para el PDF del historial).
ETIQUETA_EVENTO = {
    "inicio": "Inicio de sesión",
    "cierre": "Cierre de sesión",
    "fallido": "Intento fallido",
    "bloqueo": "Usuario bloqueado",
    "intento_bloqueado": "Intento bloqueado",
    "recuperacion": "Contraseña recuperada",
    "recuperacion_fallida": "Recuperación fallida",
    "codigo_generado": "Código generado",
    "cambio_password": "Contraseña cambiada",
    "venta_anulada": "Venta anulada",
}
