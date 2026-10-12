from helpers import permisos, sesion
from helpers.seguridad import verificar_password
from models import acceso, usuario


def listar_cuentas_editables():
    """
    Cuentas cuya contrasena puede cambiar el administrador en sesion:
    primero la suya y despues las de ventas. Lista de (texto, id_usuario).
    """
    if not permisos.es_admin():
        return []

    actual = sesion.obtener_usuario_actual()
    cuentas = [(f"Mi cuenta ({actual['usuario']})", actual["id_usuario"])]
    for fila in usuario.listar_usuarios_por_rol("vendedor"):
        cuentas.append((f"Ventas: {fila['nombre']} ({fila['usuario']})", fila["id_usuario"]))
    return cuentas


def cambiar_password(id_usuario, password_admin, password_nueva, confirmacion):
    """
    Cambia la contrasena de una cuenta. Solo un administrador puede
    hacerlo y siempre debe confirmar con su contrasena actual.

    Devuelve (exito, mensaje, campo) donde campo indica que entrada
    tiene el problema: "actual", "nueva", "confirmacion" o None.
    """
    actual = sesion.obtener_usuario_actual()
    if actual is None or not permisos.es_admin():
        return False, "Solo el administrador puede cambiar contraseñas.", None

    if not password_admin:
        return False, "Escribe tu contraseña actual.", "actual"

    fila_admin = usuario.obtener_usuario_por_id(actual["id_usuario"])
    if fila_admin is None or not verificar_password(password_admin, fila_admin["password_hash"]):
        return False, "La contraseña actual no es correcta.", "actual"

    if len(password_nueva) < 6:
        return False, "La nueva contraseña debe tener al menos 6 caracteres.", "nueva"

    if password_nueva != confirmacion:
        return False, "La confirmación no coincide con la nueva contraseña.", "confirmacion"

    destino = usuario.obtener_usuario_por_id(id_usuario)
    if destino is None or not destino["estado"]:
        return False, "La cuenta seleccionada no existe.", None
    if destino["id_usuario"] != actual["id_usuario"] and destino["rol"] != "vendedor":
        return False, "Solo puedes cambiar tu contraseña o la de las cuentas de ventas.", None

    if verificar_password(password_nueva, destino["password_hash"]):
        return False, "La nueva contraseña debe ser distinta de la actual.", "nueva"

    usuario.actualizar_password(id_usuario, password_nueva)
    acceso.registrar_evento(destino["usuario"], "cambio_password", destino["id_usuario"],
                            f"Cambiada por {actual['usuario']}")

    if destino["id_usuario"] == actual["id_usuario"]:
        return True, "Tu contraseña se actualizó.", None
    return True, f"Se actualizó la contraseña de '{destino['usuario']}'.", None
