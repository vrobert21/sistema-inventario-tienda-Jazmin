"""
Modelo de Usuarios.
"""

from database.conexion import obtener_conexion
from helpers.seguridad import generar_hash


def contar_usuarios():
    """
    Devuelve cuantos usuarios existen en total. Se usa al
    arrancar el programa para saber si hay que crear un
    usuario administrador por defecto (ver database/conexion.py).
    """
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("SELECT COUNT(*) AS total FROM usuarios;")
    resultado = cursor.fetchone()
    conexion.close()

    return resultado["total"]


def obtener_usuario_por_login(nombre_usuario):
    """
    Busca un usuario por su nombre de login (columna 'usuario').
    Devuelve la fila si existe y esta activo, o None si no.

    Nota: el filtro "estado = 1" esta aqui a proposito. Un
    usuario desactivado NO debe poder iniciar sesion, aunque
    escriba la contrasena correcta - por eso ni siquiera lo
    devolvemos, para que el controlador lo trate igual que un
    usuario que no existe (mensaje generico, sin revelar si el
    problema fue "no existe" o "esta desactivado").
    """
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT id_usuario, nombre, usuario, password_hash, rol, estado "
        "FROM usuarios WHERE usuario = ? AND estado = 1;",
        (nombre_usuario,)
    )
    fila = cursor.fetchone()
    conexion.close()

    return fila


def crear_usuario(nombre, usuario, password, rol):
    """
    Inserta un nuevo usuario, guardando la contrasena ya
    convertida en hash (nunca en texto plano).
    """
    nombre = nombre.strip()
    usuario = usuario.strip()

    if not nombre or not usuario:
        raise ValueError("El nombre y el usuario no pueden estar vacios.")

    if rol not in ("admin", "vendedor"):
        raise ValueError("El rol debe ser 'admin' o 'vendedor'.")

    if len(password) < 6:
        raise ValueError("La contrasena debe tener al menos 6 caracteres.")

    password_hash = generar_hash(password)

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        cursor.execute(
            "INSERT INTO usuarios (nombre, usuario, password_hash, rol, estado) "
            "VALUES (?, ?, ?, ?, 1);",
            (nombre, usuario, password_hash, rol)
        )
        conexion.commit()
        nuevo_id = cursor.lastrowid
    except Exception as error:
        # sqlite3.IntegrityError salta aqui si el "usuario"
        # (login) ya existe, porque la columna tiene UNIQUE en
        # el schema. La convertimos en un mensaje claro.
        conexion.close()
        if "UNIQUE" in str(error):
            raise ValueError(f"El nombre de usuario '{usuario}' ya existe.")
        raise

    conexion.close()
    return nuevo_id


def contar_usuarios_por_rol(rol):
    """Cuantos usuarios activos tienen el rol indicado."""
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT COUNT(*) AS total FROM usuarios WHERE rol = ? AND estado = 1;",
        (rol,)
    )
    resultado = cursor.fetchone()
    conexion.close()

    return resultado["total"]


def obtener_usuario_por_id(id_usuario):
    """Devuelve la fila del usuario (activo o no), o None si no existe."""
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT id_usuario, nombre, usuario, password_hash, rol, estado "
        "FROM usuarios WHERE id_usuario = ?;",
        (id_usuario,)
    )
    fila = cursor.fetchone()
    conexion.close()

    return fila


def listar_usuarios_por_rol(rol):
    """Usuarios activos de un rol (sin el hash de la contrasena)."""
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT id_usuario, nombre, usuario, rol FROM usuarios "
        "WHERE rol = ? AND estado = 1 ORDER BY nombre;",
        (rol,)
    )
    filas = cursor.fetchall()
    conexion.close()

    return filas


def actualizar_password(id_usuario, password_nueva):
    """Guarda una nueva contrasena (como hash) para el usuario."""
    if len(password_nueva) < 6:
        raise ValueError("La contrasena debe tener al menos 6 caracteres.")

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        "UPDATE usuarios SET password_hash = ? WHERE id_usuario = ?;",
        (generar_hash(password_nueva), id_usuario)
    )
    conexion.commit()
    actualizados = cursor.rowcount
    conexion.close()

    return actualizados == 1


def tiene_codigo_recuperacion(id_usuario):
    """True si el usuario ya tiene un codigo de recuperacion vigente."""
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT codigo_recuperacion_hash FROM usuarios WHERE id_usuario = ?;",
        (id_usuario,)
    )
    fila = cursor.fetchone()
    conexion.close()

    return fila is not None and bool(fila["codigo_recuperacion_hash"])


def obtener_hash_codigo_recuperacion(id_usuario):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT codigo_recuperacion_hash FROM usuarios WHERE id_usuario = ?;",
        (id_usuario,)
    )
    fila = cursor.fetchone()
    conexion.close()

    return fila["codigo_recuperacion_hash"] if fila else None


def guardar_codigo_recuperacion(id_usuario, codigo_normalizado):
    """Guarda el hash del codigo de recuperacion (reemplaza el anterior)."""
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        "UPDATE usuarios SET codigo_recuperacion_hash = ? WHERE id_usuario = ?;",
        (generar_hash(codigo_normalizado), id_usuario)
    )
    conexion.commit()
    conexion.close()


def crear_usuarios_por_defecto():
    """
    Garantiza que existan las dos cuentas del sistema:

    - Administrador (logistica: inventario, productos, categorias, reportes)
        Usuario: admin     Contrasena: admin123
    - Ventas (ventas, creditos y clientes)
        Usuario: ventas    Contrasena: ventas123

    Solo crea la cuenta de un rol si no hay ningun usuario activo con
    ese rol, asi que no toca las cuentas que ya existen. Devuelve la
    lista de (usuario, contrasena) creados para avisar al arrancar.

    Cambia estas contrasenas desde "Cambiar contrasena" (sesion de
    administrador) antes de usar el sistema en produccion.
    """
    creados = []
    for rol, nombre, login, password in (
        ("admin", "Administrador", "admin", "admin123"),
        ("vendedor", "Ventas", "ventas", "ventas123"),
    ):
        if contar_usuarios_por_rol(rol) == 0:
            crear_usuario(nombre=nombre, usuario=login, password=password, rol=rol)
            creados.append((login, password))
    return creados
