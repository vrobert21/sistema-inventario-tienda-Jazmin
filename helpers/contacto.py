"""
Datos de contacto del administrador.

Se muestran en la pantalla de inicio de sesion cuando falla un intento
(contrasena incorrecta, usuario bloqueado, etc.), para que la persona
sepa a quien acudir en vez de quedarse sin saber que hacer.

Cambia TELEFONO_ADMIN y CORREO_ADMIN por los datos reales de la tienda.
Deja uno vacio ("") si no aplica.
"""

TELEFONO_ADMIN = "6867-6948"
CORREO_ADMIN = "jorgeperza73@gmail.com"


def mensaje_contacto():
    """Texto listo para mostrar, o '' si no hay ningun dato configurado."""
    partes = [p for p in (TELEFONO_ADMIN, CORREO_ADMIN) if p]
    if not partes:
        return ""
    return "¿No puedes entrar? Contacta al administrador: " + " o al correo: ".join(partes)
