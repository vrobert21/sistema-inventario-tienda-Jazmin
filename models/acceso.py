"""
Modelo de accesos al sistema.

- historial_accesos: cada inicio de sesion, intento fallido, bloqueo,
  cierre de sesion y recuperacion de contrasena.
- intentos_login: contador de intentos fallidos seguidos por usuario,
  usado para el bloqueo temporal contra fuerza bruta.
"""

from datetime import datetime, timedelta

from database.conexion import obtener_conexion

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


# ------------------------------------------------------------
# Historial
# ------------------------------------------------------------

def registrar_evento(usuario, evento, id_usuario=None, detalle=None):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        "INSERT INTO historial_accesos (usuario, id_usuario, evento, detalle) "
        "VALUES (?, ?, ?, ?);",
        (usuario, id_usuario, evento, detalle)
    )
    conexion.commit()
    conexion.close()


def listar_historial(limite=1000):
    """Eventos mas recientes primero, con el nombre de la cuenta si existe."""
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT h.id_acceso, h.fecha, h.usuario, h.evento, h.detalle, "
        "       u.nombre AS nombre, u.rol AS rol "
        "FROM historial_accesos h "
        "LEFT JOIN usuarios u ON u.id_usuario = h.id_usuario "
        "ORDER BY h.fecha DESC, h.id_acceso DESC LIMIT ?;",
        (limite,)
    )
    filas = cursor.fetchall()
    conexion.close()

    return filas


# ------------------------------------------------------------
# Intentos fallidos y bloqueo temporal
# ------------------------------------------------------------

def _clave(usuario):
    return (usuario or "").strip().lower()


def segundos_de_bloqueo(usuario):
    """
    Segundos que le faltan al bloqueo de este usuario (0 si no esta
    bloqueado). Si el bloqueo ya vencio, reinicia el contador.
    """
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT bloqueado_hasta FROM intentos_login WHERE usuario = ?;",
        (_clave(usuario),)
    )
    fila = cursor.fetchone()

    restante = 0
    if fila is not None and fila["bloqueado_hasta"]:
        hasta = datetime.strptime(fila["bloqueado_hasta"], _FORMATO_FECHA)
        restante = int((hasta - datetime.now()).total_seconds())
        if restante <= 0:
            cursor.execute("DELETE FROM intentos_login WHERE usuario = ?;", (_clave(usuario),))
            conexion.commit()
            restante = 0

    conexion.close()
    return restante


def registrar_intento_fallido(usuario, max_intentos, minutos_bloqueo):
    """
    Suma un intento fallido. Al llegar a max_intentos bloquea al
    usuario durante minutos_bloqueo.

    Devuelve (intentos_acumulados, quedo_bloqueado).
    """
    clave = _clave(usuario)
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        "INSERT INTO intentos_login (usuario, intentos) VALUES (?, 1) "
        "ON CONFLICT(usuario) DO UPDATE SET intentos = intentos + 1;",
        (clave,)
    )
    cursor.execute("SELECT intentos FROM intentos_login WHERE usuario = ?;", (clave,))
    intentos = cursor.fetchone()["intentos"]

    bloqueado = intentos >= max_intentos
    if bloqueado:
        hasta = datetime.now() + timedelta(minutes=minutos_bloqueo)
        cursor.execute(
            "UPDATE intentos_login SET bloqueado_hasta = ? WHERE usuario = ?;",
            (hasta.strftime(_FORMATO_FECHA), clave)
        )

    conexion.commit()
    conexion.close()
    return intentos, bloqueado


def limpiar_intentos(usuario):
    """Se llama tras un inicio de sesion o recuperacion correctos."""
    conexion = obtener_conexion()
    conexion.execute("DELETE FROM intentos_login WHERE usuario = ?;", (_clave(usuario),))
    conexion.commit()
    conexion.close()
