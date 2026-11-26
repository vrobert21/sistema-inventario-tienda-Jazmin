
from models import venta, producto, acceso
from helpers import permisos, sesion
from helpers.formato import centavos_a_texto


def obtener_productos_para_venta():
    todos = producto.listar_productos(solo_activos=True)
    return [p for p in todos if p["existencia"] > 0]


def registrar_venta(tipo_pago, id_cliente, carrito):
    
    usuario_actual = sesion.obtener_usuario_actual()

    if usuario_actual is None:
        return False, "No hay una sesion activa.", None

    try:
        resultado = venta.registrar_venta(
            id_usuario=usuario_actual["id_usuario"],
            tipo_pago=tipo_pago,
            id_cliente=id_cliente,
            items=carrito,
        )
        return True, f"Venta {resultado['numero_venta']} registrada correctamente.", resultado
    except ValueError as error:
        return False, str(error), None
    except Exception as error:
        return False, f"Error inesperado: {error}", None


def obtener_ventas_recientes():
    return venta.listar_ventas_recientes()


def anular_venta(id_venta):
    """
    Anula una venta: regresa el inventario vendido y, si era al
    credito, revierte el cargo al cliente. Solo el administrador
    puede hacerlo, y queda registrado en el historial de accesos.

    Devuelve (exito, mensaje).
    """
    if not permisos.es_admin():
        return False, "Solo el administrador puede anular una venta."

    usuario_actual = sesion.obtener_usuario_actual()
    if usuario_actual is None:
        return False, "No hay una sesión activa."

    try:
        resultado = venta.anular_venta(id_venta, usuario_actual["id_usuario"])
    except ValueError as error:
        return False, str(error)
    except Exception as error:
        return False, f"Error inesperado: {error}"

    acceso.registrar_evento(
        usuario_actual["usuario"], "venta_anulada", usuario_actual["id_usuario"],
        f"Venta {resultado['numero_venta']} anulada "
        f"({centavos_a_texto(resultado['total'])})",
    )
    return True, f"Venta {resultado['numero_venta']} anulada correctamente."
