"""
Inicio de sesion, cierre de sesion y recuperacion de contrasena.

Proteccion contra fuerza bruta: tras MAX_INTENTOS intentos fallidos
seguidos (de inicio de sesion o de recuperacion) el usuario queda
bloqueado MINUTOS_BLOQUEO minutos. Todo queda en historial_accesos.
"""

from helpers import sesion
from helpers.seguridad import (
    generar_codigo_recuperacion, normalizar_codigo, verificar_password,
)
from models import acceso, usuario

MAX_INTENTOS = 5
MINUTOS_BLOQUEO = 5


def _texto_espera(segundos):
    minutos, resto = divmod(max(segundos, 1), 60)
    if minutos == 0:
        return f"{resto} segundos"
    if resto == 0:
        return "1 minuto" if minutos == 1 else f"{minutos} minutos"
    return f"{minutos} min {resto} s"


def _mensaje_bloqueo(segundos):
    return ("Por seguridad, este usuario está bloqueado temporalmente por demasiados "
            f"intentos fallidos. Intenta de nuevo en {_texto_espera(segundos)}.")


def _id_de(nombre_usuario):
    fila = usuario.obtener_usuario_por_login(nombre_usuario)
    return fila["id_usuario"] if fila else None


def _registrar_fallo(nombre_usuario, id_usuario, evento, mensaje_error):
    """Suma el intento fallido y devuelve el mensaje a mostrar."""
    intentos, bloqueado = acceso.registrar_intento_fallido(
        nombre_usuario, MAX_INTENTOS, MINUTOS_BLOQUEO
    )
    acceso.registrar_evento(nombre_usuario, evento, id_usuario,
                            f"Intento {intentos} de {MAX_INTENTOS}")
    if bloqueado:
        acceso.registrar_evento(nombre_usuario, "bloqueo", id_usuario,
                                f"Bloqueado {MINUTOS_BLOQUEO} minutos")
        return _mensaje_bloqueo(MINUTOS_BLOQUEO * 60)

    restantes = MAX_INTENTOS - intentos
    if restantes <= 2:
        aviso = "Te queda 1 intento" if restantes == 1 else f"Te quedan {restantes} intentos"
        return f"{mensaje_error} {aviso} antes del bloqueo temporal."
    return mensaje_error


def iniciar_sesion(nombre_usuario, password):

    nombre_usuario = nombre_usuario.strip()

    if not nombre_usuario or not password:
        return False, "Debes ingresar usuario y contrasena."

    segundos = acceso.segundos_de_bloqueo(nombre_usuario)
    if segundos > 0:
        acceso.registrar_evento(nombre_usuario, "intento_bloqueado", _id_de(nombre_usuario),
                                "Intento durante el bloqueo")
        return False, _mensaje_bloqueo(segundos)

    fila_usuario = usuario.obtener_usuario_por_login(nombre_usuario)

    if fila_usuario is None or not verificar_password(password, fila_usuario["password_hash"]):
        id_usuario = fila_usuario["id_usuario"] if fila_usuario else None
        return False, _registrar_fallo(nombre_usuario, id_usuario, "fallido",
                                       "Usuario o contraseña incorrectos.")

    acceso.limpiar_intentos(nombre_usuario)
    acceso.registrar_evento(nombre_usuario, "inicio", fila_usuario["id_usuario"])

    sesion.iniciar_sesion({
        "id_usuario": fila_usuario["id_usuario"],
        "nombre": fila_usuario["nombre"],
        "usuario": fila_usuario["usuario"],
        "rol": fila_usuario["rol"],
    })

    return True, f"Bienvenido, {fila_usuario['nombre']}."


def cerrar_sesion():
    """Registra el cierre en el historial y limpia la sesion."""
    actual = sesion.obtener_usuario_actual()
    if actual is not None:
        acceso.registrar_evento(actual["usuario"], "cierre", actual["id_usuario"])
    sesion.cerrar_sesion()


# ------------------------------------------------------------
# Codigo de recuperacion
# ------------------------------------------------------------

def _nuevo_codigo(id_usuario):
    codigo = generar_codigo_recuperacion()
    usuario.guardar_codigo_recuperacion(id_usuario, normalizar_codigo(codigo))
    return codigo


def asegurar_codigo_recuperacion():
    """
    Si el usuario en sesion aun no tiene codigo de recuperacion, crea
    uno y lo devuelve para mostrarlo una sola vez. Si ya tiene, None.
    """
    actual = sesion.obtener_usuario_actual()
    if actual is None or usuario.tiene_codigo_recuperacion(actual["id_usuario"]):
        return None
    codigo = _nuevo_codigo(actual["id_usuario"])
    acceso.registrar_evento(actual["usuario"], "codigo_generado", actual["id_usuario"],
                            "Primer código de recuperación")
    return codigo


def regenerar_codigo_recuperacion(password):
    """
    Crea un codigo nuevo para el usuario en sesion (el anterior deja de
    servir). Pide su contrasena por si la sesion quedo abierta.

    Devuelve (exito, mensaje, codigo).
    """
    actual = sesion.obtener_usuario_actual()
    if actual is None:
        return False, "No hay una sesión activa.", None

    fila = usuario.obtener_usuario_por_id(actual["id_usuario"])
    if fila is None or not verificar_password(password or "", fila["password_hash"]):
        return False, "La contraseña no es correcta.", None

    codigo = _nuevo_codigo(actual["id_usuario"])
    acceso.registrar_evento(actual["usuario"], "codigo_generado", actual["id_usuario"],
                            "Código regenerado por el usuario")
    return True, "Se generó un nuevo código de recuperación.", codigo


def recuperar_password(nombre_usuario, codigo, password_nueva, confirmacion):
    """
    Cambia la contrasena usando el codigo de recuperacion. El codigo es
    de un solo uso: al terminar se genera otro y se devuelve para que el
    usuario lo guarde.

    Devuelve (exito, mensaje, campo, codigo_nuevo). campo indica la
    entrada con problema: "usuario", "codigo", "nueva", "confirmacion" o None.
    """
    nombre_usuario = (nombre_usuario or "").strip()

    if not nombre_usuario:
        return False, "Escribe tu usuario.", "usuario", None
    if not normalizar_codigo(codigo):
        return False, "Escribe tu código de recuperación.", "codigo", None
    if len(password_nueva) < 6:
        return False, "La nueva contraseña debe tener al menos 6 caracteres.", "nueva", None
    if password_nueva != confirmacion:
        return False, "La confirmación no coincide con la nueva contraseña.", "confirmacion", None

    segundos = acceso.segundos_de_bloqueo(nombre_usuario)
    if segundos > 0:
        acceso.registrar_evento(nombre_usuario, "intento_bloqueado", _id_de(nombre_usuario),
                                "Recuperación durante el bloqueo")
        return False, _mensaje_bloqueo(segundos), None, None

    fila = usuario.obtener_usuario_por_login(nombre_usuario)
    hash_codigo = usuario.obtener_hash_codigo_recuperacion(fila["id_usuario"]) if fila else None

    if not hash_codigo or not verificar_password(normalizar_codigo(codigo), hash_codigo):
        id_usuario = fila["id_usuario"] if fila else None
        mensaje = _registrar_fallo(nombre_usuario, id_usuario, "recuperacion_fallida",
                                   "Usuario o código de recuperación incorrectos.")
        return False, mensaje, "codigo", None

    usuario.actualizar_password(fila["id_usuario"], password_nueva)
    codigo_nuevo = _nuevo_codigo(fila["id_usuario"])
    acceso.limpiar_intentos(nombre_usuario)
    acceso.registrar_evento(nombre_usuario, "recuperacion", fila["id_usuario"],
                            "Contraseña restablecida con código")

    return True, "Tu contraseña se actualizó. Ya puedes iniciar sesión.", None, codigo_nuevo
