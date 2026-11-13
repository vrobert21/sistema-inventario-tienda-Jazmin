"""
Modelo de Categorias.

Un "modelo" en este proyecto es simplemente un archivo con
funciones que saben como leer y escribir una tabla especifica
de la base de datos. La vista y el controlador NUNCA deberian
escribir SQL directamente - siempre pasan por aqui.

Esto es equivalente a lo que hacia tu model.php en PHP: aislar
las consultas SQL en un solo lugar, para que si cambias de
motor de base de datos (o si hay un bug en una consulta), solo
tengas que tocar este archivo.
"""

import re
import sqlite3
import unicodedata

from database.conexion import obtener_conexion


def _limpiar_nombre(nombre):
    """Quita espacios sobrantes (tambien los repetidos dentro del nombre)."""
    return re.sub(r"\s+", " ", (nombre or "")).strip()


def _clave_comparacion(nombre):
    """
    Forma "canonica" del nombre para detectar repetidos: sin mayusculas,
    sin tildes y sin espacios extra. Asi "Lacteos", "lácteos" y
    " LÁCTEOS " cuentan como la MISMA categoria.

    Se hace en Python y no en SQL porque lower() de SQLite solo entiende
    letras ASCII (no sabe que "Á" y "á" son la misma letra).
    """
    texto = unicodedata.normalize("NFD", _limpiar_nombre(nombre))
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto.casefold()


def _existe_nombre(cursor, nombre, excluir_id=None):
    """True si otra categoria (distinta de excluir_id) ya tiene ese nombre."""
    clave = _clave_comparacion(nombre)
    cursor.execute("SELECT id_categoria, nombre FROM categorias;")
    for fila in cursor.fetchall():
        if fila["id_categoria"] == excluir_id:
            continue
        if _clave_comparacion(fila["nombre"]) == clave:
            return True
    return False


def listar_categorias(solo_activas=False):
    """
    Devuelve una lista de todas las categorias.

    El parametro solo_activas es opcional (por eso tiene un
    valor por defecto, False). Si se llama listar_categorias()
    sin argumentos, trae todas. Si se llama
    listar_categorias(solo_activas=True), trae solo las que
    tienen estado = 1.
    """
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    # total_productos cuenta TODOS los productos de la categoria (activos
    # e inactivos), porque cualquiera de ellos impide eliminarla.
    consulta = (
        "SELECT c.id_categoria, c.nombre, c.estado, "
        "       (SELECT COUNT(*) FROM productos p "
        "        WHERE p.id_categoria = c.id_categoria) AS total_productos "
        "FROM categorias c "
    )
    if solo_activas:
        consulta += "WHERE c.estado = 1 "
    consulta += "ORDER BY c.nombre;"
    cursor.execute(consulta)

    # fetchall() trae todas las filas del resultado. Gracias al
    # row_factory que configuramos en conexion.py, cada fila se
    # puede leer como diccionario (fila["nombre"]).
    filas = cursor.fetchall()
    conexion.close()

    return filas


def crear_categoria(nombre):
    """
    Inserta una nueva categoria. Devuelve el id_categoria
    generado, o lanza un ValueError si el nombre esta vacio.

    Nota: aqui validamos que el nombre no este vacio ANTES de
    tocar la base de datos. La tabla no tiene una restriccion
    CHECK para esto porque un nombre vacio ("") es tecnicamente
    un TEXT valido para SQLite - la regla de "no puede estar
    vacio" es una regla de negocio, no de tipo de dato, y esas
    se validan en el modelo o el controlador, no en el schema.
    """
    nombre = _limpiar_nombre(nombre)  # quita espacios sobrantes

    if not nombre:
        raise ValueError("El nombre de la categoria no puede estar vacio.")

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    # Regla de negocio: no puede haber dos categorias con el mismo nombre
    # (sin importar mayusculas, tildes o espacios extra).
    if _existe_nombre(cursor, nombre):
        conexion.close()
        raise ValueError(f"Ya existe una categoria llamada '{nombre}'.")

    # El "?" es un marcador de posicion (placeholder). SQLite
    # sustituye el "?" por el valor de forma segura, evitando
    # SQL Injection. NUNCA se debe armar la consulta pegando
    # el valor directamente en el texto (ej. f"...'{nombre}'"),
    # porque eso es justo lo que permite ataques de inyeccion SQL.
    cursor.execute(
        "INSERT INTO categorias (nombre, estado) VALUES (?, 1);",
        (nombre,)
    )

    conexion.commit()
    nuevo_id = cursor.lastrowid  # id autogenerado de la fila insertada
    conexion.close()

    return nuevo_id


def obtener_categoria(id_categoria):
    """Devuelve la categoria (con su total de productos) o None si no existe."""
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        "SELECT c.id_categoria, c.nombre, c.estado, "
        "       (SELECT COUNT(*) FROM productos p "
        "        WHERE p.id_categoria = c.id_categoria) AS total_productos "
        "FROM categorias c WHERE c.id_categoria = ?;",
        (id_categoria,)
    )
    fila = cursor.fetchone()
    conexion.close()
    return fila


def actualizar_categoria(id_categoria, nombre):
    """
    Cambia el nombre de una categoria. Lanza ValueError si el nombre esta
    vacio, si la categoria ya no existe o si OTRA categoria ya usa ese nombre.

    Se excluye a la propia categoria de la comparacion para poder guardarla
    sin cambios, o corregir solo mayusculas/tildes ("bebidas" -> "Bebidas").
    Los productos no se tocan: apuntan al id, no al nombre.
    """
    nombre = _limpiar_nombre(nombre)

    if not nombre:
        raise ValueError("El nombre de la categoria no puede estar vacio.")

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        "SELECT 1 FROM categorias WHERE id_categoria = ?;", (id_categoria,)
    )
    if cursor.fetchone() is None:
        conexion.close()
        raise ValueError("La categoria ya no existe.")

    if _existe_nombre(cursor, nombre, excluir_id=id_categoria):
        conexion.close()
        raise ValueError(f"Ya existe una categoria llamada '{nombre}'.")

    cursor.execute(
        "UPDATE categorias SET nombre = ? WHERE id_categoria = ?;",
        (nombre, id_categoria)
    )
    conexion.commit()
    conexion.close()


def eliminar_categoria(id_categoria):
    """
    Elimina una categoria SOLO si ningun producto registrado la usa
    (cuentan tambien los productos desactivados, porque siguen existiendo
    en el catalogo y en el historial). Si tiene productos lanza ValueError
    indicando cuantos son.

    La comprobacion y el borrado ocurren en la misma conexion, y ademas
    la clave foranea de la tabla productos (PRAGMA foreign_keys = ON)
    actua como ultima barrera.
    """
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    cursor.execute(
        "SELECT nombre FROM categorias WHERE id_categoria = ?;", (id_categoria,)
    )
    fila = cursor.fetchone()
    if fila is None:
        conexion.close()
        raise ValueError("La categoria ya no existe.")

    cursor.execute(
        "SELECT COUNT(*) AS total FROM productos WHERE id_categoria = ?;",
        (id_categoria,)
    )
    total = cursor.fetchone()["total"]
    if total > 0:
        conexion.close()
        plural = "producto registrado" if total == 1 else "productos registrados"
        raise ValueError(
            f"No se puede eliminar '{fila['nombre']}': tiene {total} {plural}. "
            "Cambia esos productos a otra categoria primero."
        )

    try:
        cursor.execute(
            "DELETE FROM categorias WHERE id_categoria = ?;", (id_categoria,)
        )
        conexion.commit()
    except sqlite3.IntegrityError:
        conexion.rollback()
        raise ValueError(
            f"No se puede eliminar '{fila['nombre']}': esta en uso por un producto."
        )
    finally:
        conexion.close()

    return fila["nombre"]


if __name__ == "__main__":
    # Prueba rapida y aislada de este modelo, sin pasar por la
    # interfaz grafica. Sirve para confirmar que el modelo
    # funciona antes de conectarlo con la vista.
    from database.conexion import inicializar_base_datos
    inicializar_base_datos()

    print("Categorias antes de insertar:", listar_categorias())

    id_nueva = crear_categoria("Bebidas")
    print(f"Categoria creada con id {id_nueva}")

    print("Categorias despues de insertar:", listar_categorias())
