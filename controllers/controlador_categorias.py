
import re

from models import categoria


def obtener_lista_categorias():
    return categoria.listar_categorias()


def obtener_categoria_por_id(id_categoria):
    return categoria.obtener_categoria(id_categoria)


def _nombre_limpio(nombre):
    return re.sub(r"\s+", " ", nombre or "").strip()


def registrar_categoria(nombre):

    try:
        categoria.crear_categoria(nombre)
        return True, f"Categoria '{_nombre_limpio(nombre)}' registrada correctamente."
    except ValueError as error:
        return False, str(error)
    except Exception as error:
        return False, f"Error inesperado: {error}"


def modificar_categoria(id_categoria, nombre):
    try:
        categoria.actualizar_categoria(id_categoria, nombre)
        return True, f"Categoria '{_nombre_limpio(nombre)}' actualizada correctamente."
    except ValueError as error:
        return False, str(error)
    except Exception as error:
        return False, f"Error inesperado: {error}"


def eliminar_categoria(id_categoria):
    try:
        nombre = categoria.eliminar_categoria(id_categoria)
        return True, f"Categoria '{nombre}' eliminada correctamente."
    except ValueError as error:
        return False, str(error)
    except Exception as error:
        return False, f"Error inesperado: {error}"
