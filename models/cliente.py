"""
Modelo de Clientes.
"""

from database.conexion import obtener_conexion


def listar_clientes(solo_activos=False):
    conexion = obtener_conexion()
    cursor = conexion.cursor()

    consulta = "SELECT * FROM clientes"
    if solo_activos:
        consulta += " WHERE estado = 1"
    consulta += " ORDER BY nombre_completo;"

    cursor.execute(consulta)
    filas = cursor.fetchall()
    conexion.close()
    return filas


def obtener_cliente(id_cliente):
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute("SELECT * FROM clientes WHERE id_cliente = ?;", (id_cliente,))
    fila = cursor.fetchone()
    conexion.close()
    return fila


def _validar_datos_cliente(nombre_completo, telefono):
    """
    Solo nombre y telefono son obligatorios, tal como se acordo
    en el analisis inicial (Etapa 1): para una tienda pequena,
    pedir DUI, direccion o correo de forma obligatoria agrega
    friccion innecesaria al registrar un cliente rapido en el
    mostrador.
    """
    if not nombre_completo.strip():
        raise ValueError("El nombre del cliente no puede estar vacio.")
    if not telefono.strip():
        raise ValueError("El telefono del cliente no puede estar vacio.")


def _verificar_cliente_duplicado(nombre_completo, telefono, dui=None,
                                 excluir_id=None):
    """
    Rechaza (ValueError) el registro si OTRO cliente ya tiene:
      - el mismo DUI (solo cuando se indica un DUI), o
      - el mismo nombre y telefono (sin distinguir mayusculas).

    excluir_id: al editar, id del propio cliente para no compararlo
    consigo mismo. Al crear se deja en None.
    """
    def normalizar(texto):
        return (texto or "").strip().casefold()

    nombre_n = normalizar(nombre_completo)
    telefono_n = normalizar(telefono)
    dui_n = normalizar(dui)

    conexion = obtener_conexion()
    try:
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT id_cliente, nombre_completo, telefono, dui FROM clientes;"
        )
        filas = cursor.fetchall()
    finally:
        conexion.close()

    for fila in filas:
        id_existente, nombre_ex, telefono_ex, dui_ex = (
            fila[0], fila[1], fila[2], fila[3]
        )
        if excluir_id is not None and id_existente == excluir_id:
            continue
        if dui_n and normalizar(dui_ex) == dui_n:
            raise ValueError(
                f"Ya existe un cliente registrado con el DUI {dui.strip()}."
            )
        if normalizar(nombre_ex) == nombre_n and normalizar(telefono_ex) == telefono_n:
            raise ValueError(
                "Ya existe un cliente con el mismo nombre y telefono."
            )


def crear_cliente(nombre_completo, telefono, dui, direccion, correo, limite_credito):
    """
    limite_credito llega ya convertido a centavos (o None si se
    dejo en blanco) - esa conversion la hace el controlador,
    igual que con los precios de productos.
    """
    _validar_datos_cliente(nombre_completo, telefono)
    _verificar_cliente_duplicado(nombre_completo, telefono, dui)

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        """
        INSERT INTO clientes
            (nombre_completo, telefono, dui, direccion, correo,
             limite_credito, estado)
        VALUES (?, ?, ?, ?, ?, ?, 1);
        """,
        (nombre_completo.strip(), telefono.strip(),
         dui.strip() or None, direccion.strip() or None,
         correo.strip() or None, limite_credito)
    )
    conexion.commit()
    nuevo_id = cursor.lastrowid
    conexion.close()
    return nuevo_id


def actualizar_cliente(id_cliente, nombre_completo, telefono, dui, direccion,
                        correo, limite_credito):
    _validar_datos_cliente(nombre_completo, telefono)
    _verificar_cliente_duplicado(nombre_completo, telefono, dui,
                                 excluir_id=id_cliente)

    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        """
        UPDATE clientes
        SET nombre_completo = ?, telefono = ?, dui = ?, direccion = ?,
            correo = ?, limite_credito = ?
        WHERE id_cliente = ?;
        """,
        (nombre_completo.strip(), telefono.strip(),
         dui.strip() or None, direccion.strip() or None,
         correo.strip() or None, limite_credito, id_cliente)
    )
    conexion.commit()
    conexion.close()


def cambiar_estado_cliente(id_cliente, nuevo_estado):
    """
    Igual que con productos: no se borra un cliente fisicamente
    (rompe la relacion con ventas y pagos ya registrados), se
    desactiva.
    """
    conexion = obtener_conexion()
    cursor = conexion.cursor()
    cursor.execute(
        "UPDATE clientes SET estado = ? WHERE id_cliente = ?;",
        (nuevo_estado, id_cliente)
    )
    conexion.commit()
    conexion.close()
