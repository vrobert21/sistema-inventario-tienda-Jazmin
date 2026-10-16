"""
Permisos por rol.

El sistema separa el trabajo en dos cuentas:

- admin    -> todas las secciones del programa. Tambien puede cambiar las
              contrasenas y ver la seccion de seguridad (historial de
              accesos y respaldos).
- vendedor -> parte de ventas: ventas, creditos y clientes, y los reportes.

La ventana principal solo construye las secciones que el rol puede ver,
y las pantallas usan puede_ver() para ocultar accesos a secciones ajenas.
"""

from helpers import sesion

SECCIONES_POR_ROL = {
    "admin": ("inicio", "reportes", "ventas", "creditos", "clientes",
              "inventario", "productos", "categorias", "seguridad"),
    "vendedor": ("reportes", "ventas", "creditos", "clientes"),
}

# Seccion que se abre al iniciar sesion.
SECCION_INICIAL_POR_ROL = {
    "admin": "inicio",
    "vendedor": "ventas",
}


def rol_actual():
    usuario = sesion.obtener_usuario_actual()
    return usuario["rol"] if usuario else None


def secciones_permitidas(rol=None):
    return SECCIONES_POR_ROL.get(rol or rol_actual(), ())


def seccion_inicial(rol=None):
    return SECCION_INICIAL_POR_ROL.get(rol or rol_actual())


def puede_ver(clave):
    return clave in secciones_permitidas()


def es_admin():
    return rol_actual() == "admin"
