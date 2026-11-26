"""
Modelo de Ventas.

Esta es la operacion mas compleja del sistema hasta ahora.
Registrar UNA venta implica, en realidad, escribir en TRES
tablas distintas:
  1. ventas          (la cabecera: fecha, cliente, total, etc.)
  2. detalle_ventas   (una fila por cada producto vendido)
  3. productos e movimientos_inventario (descontar existencia
     y dejar el rastro de por que bajo)

Las tres tienen que quedar consistentes JUNTAS. Por eso todo
este proceso va dentro de una sola transaccion - el mismo
concepto de la Etapa 8, pero ahora con mas pasos encadenados.
"""

from database.conexion import obtener_conexion
from models import movimiento_cuenta_cliente
from helpers.formato import centavos_a_texto

METODOS_PAGO_IMPLEMENTADOS = ("efectivo", "tarjeta", "otro", "credito")


def registrar_venta(id_usuario, tipo_pago, id_cliente, items):
    """
    Registra una venta completa.

    items: lista de diccionarios, uno por producto vendido:
        [{"id_producto": 3, "cantidad": 2}, ...]
    El precio de cada producto se lee DE LA BASE DE DATOS en
    este momento (no se confia en un precio que venga de la
    vista) - asi nos aseguramos de vender siempre al precio
    actual y real del producto, sin importar que haya cambiado
    desde que se abrio la pantalla de ventas.

    Devuelve un diccionario con id_venta, numero_venta y total
    (en centavos). Lanza ValueError si algo no es valido (sin
    stock suficiente, producto inactivo, carrito vacio, etc.).
    """
    if tipo_pago not in METODOS_PAGO_IMPLEMENTADOS:
        raise ValueError(
            f"El metodo de pago '{tipo_pago}' aun no esta disponible. "
            f"Las ventas al credito se implementan en la Etapa 11."
        )

    if not items:
        raise ValueError("La venta no puede estar vacia. Agrega al menos un producto.")

    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        # --- Paso 1: validar y calcular cada linea del carrito ---
        # Guardamos aqui los datos ya verificados de cada
        # producto, para usarlos despues al insertar. Hacemos
        # esto ANTES de escribir nada en la base de datos, para
        # poder rechazar la venta completa si algo no cuadra,
        # sin haber tocado ninguna tabla todavia.
        detalles = []
        subtotal_total = 0

        for item in items:
            id_producto = item["id_producto"]
            cantidad = item["cantidad"]

            if cantidad <= 0:
                raise ValueError("Las cantidades deben ser mayores a cero.")

            cursor.execute(
                "SELECT nombre, precio_venta, existencia, estado "
                "FROM productos WHERE id_producto = ?;",
                (id_producto,)
            )
            fila = cursor.fetchone()

            if fila is None:
                raise ValueError(f"Un producto de la venta ya no existe (id {id_producto}).")
            if fila["estado"] != 1:
                raise ValueError(f"El producto '{fila['nombre']}' esta desactivado.")
            if cantidad > fila["existencia"]:
                raise ValueError(
                    f"No hay suficiente existencia de '{fila['nombre']}'. "
                    f"Disponible: {fila['existencia']}, solicitado: {cantidad}."
                )

            precio_unitario = fila["precio_venta"]
            subtotal_linea = precio_unitario * cantidad
            subtotal_total += subtotal_linea

            detalles.append({
                "id_producto": id_producto,
                "nombre": fila["nombre"],
                "cantidad": cantidad,
                "precio_unitario": precio_unitario,
                "subtotal": subtotal_linea,
                "existencia_anterior": fila["existencia"],
            })

        total = subtotal_total  # por ahora sin impuestos ni descuentos

        # --- Paso 1.5: validaciones especificas de venta al credito ---
        # Las hacemos ANTES de insertar nada, siguiendo la misma
        # idea del Paso 1: si la venta no es valida, mejor
        # descubrirlo sin haber tocado ninguna tabla todavia.
        if tipo_pago == "credito":
            if id_cliente is None:
                raise ValueError("Debes seleccionar un cliente para una venta al credito.")

            cursor.execute(
                "SELECT nombre_completo, estado, limite_credito FROM clientes WHERE id_cliente = ?;",
                (id_cliente,)
            )
            fila_cliente = cursor.fetchone()

            if fila_cliente is None:
                raise ValueError("El cliente seleccionado no existe.")
            if fila_cliente["estado"] != 1:
                raise ValueError(f"El cliente '{fila_cliente['nombre_completo']}' esta desactivado.")

            limite_credito = fila_cliente["limite_credito"]
            if limite_credito is not None:
                saldo_actual = movimiento_cuenta_cliente.calcular_saldo_con_cursor(cursor, id_cliente)
                saldo_resultante = saldo_actual + total
                if saldo_resultante > limite_credito:
                    raise ValueError(
                        f"Esta venta excede el limite de credito de "
                        f"'{fila_cliente['nombre_completo']}'. "
                        f"Saldo actual: {centavos_a_texto(saldo_actual)}, "
                        f"limite: {centavos_a_texto(limite_credito)}, "
                        f"esta venta: {centavos_a_texto(total)}."
                    )
        elif id_cliente is not None:
            # Para ventas de contado, el cliente es opcional -
            # pero si se selecciono uno, verificamos que exista
            # y este activo, para no guardar una venta apuntando
            # a un cliente invalido.
            cursor.execute(
                "SELECT estado FROM clientes WHERE id_cliente = ?;", (id_cliente,)
            )
            fila_cliente = cursor.fetchone()
            if fila_cliente is None:
                raise ValueError("El cliente seleccionado no existe.")

        # --- Paso 2: insertar la cabecera de la venta ---
        # Insertamos primero con numero_venta vacio, porque
        # necesitamos el id_venta (que SQLite genera solo al
        # insertar) para poder construir el numero de venta.
        cursor.execute(
            """
            INSERT INTO ventas
                (numero_venta, id_cliente, id_usuario, tipo_pago,
                 subtotal, total, estado)
            VALUES ('', ?, ?, ?, ?, ?, 1);
            """,
            (id_cliente, id_usuario, tipo_pago, subtotal_total, total)
        )
        id_venta = cursor.lastrowid

        # Ahora si armamos el numero de venta visible, usando el
        # id recien generado, con ceros a la izquierda (ej. V-000001).
        numero_venta = f"V-{id_venta:06d}"
        cursor.execute(
            "UPDATE ventas SET numero_venta = ? WHERE id_venta = ?;",
            (numero_venta, id_venta)
        )

        # --- Paso 2.5: si es venta al credito, registrar el cargo ---
        # Usamos el mismo cursor (misma transaccion) que el resto
        # de la venta - si algo falla despues de esto, el
        # rollback tambien deshace este cargo.
        if tipo_pago == "credito":
            movimiento_cuenta_cliente.registrar_cargo(
                cursor, id_cliente, id_venta, total, f"Venta {numero_venta}"
            )

        # --- Paso 3: insertar cada linea y descontar inventario ---
        for d in detalles:
            cursor.execute(
                """
                INSERT INTO detalle_ventas
                    (id_venta, id_producto, cantidad, precio_unitario, subtotal)
                VALUES (?, ?, ?, ?, ?);
                """,
                (id_venta, d["id_producto"], d["cantidad"],
                 d["precio_unitario"], d["subtotal"])
            )

            existencia_nueva = d["existencia_anterior"] - d["cantidad"]

            cursor.execute(
                "UPDATE productos SET existencia = ? WHERE id_producto = ?;",
                (existencia_nueva, d["id_producto"])
            )

            # Dejamos el rastro en movimientos_inventario, igual
            # que en la Etapa 8, pero aqui insertado DIRECTAMENTE
            # con este mismo cursor - no llamando a
            # movimiento_inventario.registrar_movimiento(), porque
            # esa funcion abre su PROPIA conexion/transaccion, y
            # eso romperia la atomicidad de toda la venta.
            cursor.execute(
                """
                INSERT INTO movimientos_inventario
                    (id_producto, tipo, cantidad, existencia_anterior,
                     existencia_nueva, id_venta, descripcion)
                VALUES (?, 'salida', ?, ?, ?, ?, ?);
                """,
                (d["id_producto"], d["cantidad"], d["existencia_anterior"],
                 existencia_nueva, id_venta, f"Venta {numero_venta}")
            )

        # Si llegamos hasta aqui sin errores, todo se guarda junto.
        conexion.commit()

    except Exception:
        # Si algo fallo en cualquier paso (stock insuficiente,
        # producto inactivo, error de SQLite), deshacemos TODO:
        # ni la venta, ni el detalle, ni el descuento de
        # inventario quedan guardados a medias.
        conexion.rollback()
        raise

    finally:
        conexion.close()

    return {"id_venta": id_venta, "numero_venta": numero_venta, "total": total}


def listar_ventas_recientes(limite=20):
    """
    Devuelve las ventas mas recientes, con el nombre del
    usuario que la realizo y del cliente (si tenia uno).
    LEFT JOIN en vez de JOIN normal para clientes, porque una
    venta al contado sin cliente registrado tiene id_cliente
    en NULL - con un JOIN normal, esas ventas simplemente
    desaparecerian del resultado.
    """
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        """
        SELECT
            v.id_venta, v.numero_venta, v.fecha, v.tipo_pago,
            v.total, v.estado,
            u.nombre AS nombre_usuario,
            c.nombre_completo AS nombre_cliente
        FROM ventas v
        JOIN usuarios u ON v.id_usuario = u.id_usuario
        LEFT JOIN clientes c ON v.id_cliente = c.id_cliente
        ORDER BY v.fecha DESC, v.id_venta DESC
        LIMIT ?;
        """,
        (limite,)
    )
    filas = cursor.fetchall()
    conexion.close()
    return filas


def anular_venta(id_venta, id_usuario):
    """
    Anula una venta ya registrada: regresa al inventario lo vendido en
    cada linea (con su rastro en movimientos_inventario) y, si era una
    venta al credito, revierte el cargo hecho a la cuenta del cliente.
    La venta no se borra: queda con estado = 0 ("anulada") para
    conservar el historial completo.

    Todo el proceso va en una sola transaccion, igual que
    registrar_venta: o se deshace completo, o no se toca nada.

    Devuelve un diccionario con numero_venta y total (en centavos).
    Lanza ValueError si la venta no existe o ya estaba anulada.
    """
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    try:
        cursor.execute(
            "SELECT numero_venta, estado, tipo_pago, id_cliente, total "
            "FROM ventas WHERE id_venta = ?;",
            (id_venta,)
        )
        cabecera = cursor.fetchone()
        if cabecera is None:
            raise ValueError("Esa venta ya no existe.")
        if cabecera["estado"] == 0:
            raise ValueError(f"La venta {cabecera['numero_venta']} ya estaba anulada.")

        numero_venta = cabecera["numero_venta"]

        cursor.execute(
            "SELECT id_producto, cantidad FROM detalle_ventas WHERE id_venta = ?;",
            (id_venta,)
        )
        detalles = cursor.fetchall()

        for d in detalles:
            cursor.execute(
                "SELECT existencia FROM productos WHERE id_producto = ?;",
                (d["id_producto"],)
            )
            fila_producto = cursor.fetchone()
            # Si el producto ya no existe, no hay inventario que regresar.
            if fila_producto is None:
                continue

            existencia_anterior = fila_producto["existencia"]
            existencia_nueva = existencia_anterior + d["cantidad"]
            cursor.execute(
                "UPDATE productos SET existencia = ? WHERE id_producto = ?;",
                (existencia_nueva, d["id_producto"])
            )
            cursor.execute(
                """
                INSERT INTO movimientos_inventario
                    (id_producto, tipo, cantidad, existencia_anterior,
                     existencia_nueva, id_venta, descripcion)
                VALUES (?, 'entrada', ?, ?, ?, ?, ?);
                """,
                (d["id_producto"], d["cantidad"], existencia_anterior,
                 existencia_nueva, id_venta, f"Anulación de venta {numero_venta}")
            )

        if cabecera["tipo_pago"] == "credito" and cabecera["id_cliente"] is not None:
            saldo_anterior = movimiento_cuenta_cliente.calcular_saldo_con_cursor(
                cursor, cabecera["id_cliente"])
            saldo_nuevo = saldo_anterior - cabecera["total"]
            cursor.execute(
                """
                INSERT INTO movimientos_cuenta_cliente
                    (id_cliente, tipo, id_venta, monto, saldo_anterior, saldo_nuevo, descripcion)
                VALUES (?, 'abono', ?, ?, ?, ?, ?);
                """,
                (cabecera["id_cliente"], id_venta, cabecera["total"],
                 saldo_anterior, saldo_nuevo, f"Anulación de venta {numero_venta}")
            )

        cursor.execute("UPDATE ventas SET estado = 0 WHERE id_venta = ?;", (id_venta,))

        conexion.commit()

    except Exception:
        conexion.rollback()
        raise

    finally:
        conexion.close()

    return {"numero_venta": numero_venta, "total": cabecera["total"]}
