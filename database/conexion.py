
import sqlite3
import os
import sys

CARPETA_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_SCHEMA = os.path.join(CARPETA_ACTUAL, "schema.sql")

# En el ejecutable de PyInstaller, __file__ apunta a una carpeta temporal
# que se borra al cerrar; la base de datos va junto al .exe para conservarse.
if getattr(sys, "frozen", False):
    RUTA_BASE_DATOS = os.path.join(os.path.dirname(sys.executable), "tienda_jazmin.db")
else:
    RUTA_BASE_DATOS = os.path.join(CARPETA_ACTUAL, "tienda_jazmin.db")


def obtener_conexion():
    conexion = sqlite3.connect(RUTA_BASE_DATOS, timeout=10)

    conexion.execute("PRAGMA foreign_keys = ON;")

    conexion.row_factory = sqlite3.Row

    return conexion


def inicializar_base_datos():
    
    conexion = obtener_conexion()

    with open(RUTA_SCHEMA, "r", encoding="utf-8") as archivo:
        script_sql = archivo.read()

    conexion.executescript(script_sql)
    conexion.commit()

    _aplicar_migraciones(conexion)

    conexion.close()


def _aplicar_migraciones(conexion):

    cursor = conexion.cursor()

    # PRAGMA table_info nos da la lista de columnas de una tabla.
    cursor.execute("PRAGMA table_info(movimientos_inventario);")
    columnas_existentes = {fila["name"] for fila in cursor.fetchall()}

    if "descripcion" not in columnas_existentes:
        cursor.execute(
            "ALTER TABLE movimientos_inventario ADD COLUMN descripcion TEXT;"
        )
        conexion.commit()

    # --- Creditos: cada pago se asocia a la venta a credito que abona ---
    # (agregado con el modulo de cuentas por cobrar; la tabla 'pagos'
    # ya existia en el schema pero no guardaba a que venta correspondia
    # ni el metodo de pago).
    cursor.execute("PRAGMA table_info(pagos);")
    columnas_pagos = {fila["name"] for fila in cursor.fetchall()}

    if "id_venta" not in columnas_pagos:
        cursor.execute("ALTER TABLE pagos ADD COLUMN id_venta INTEGER REFERENCES ventas(id_venta);")
    if "metodo_pago" not in columnas_pagos:
        cursor.execute("ALTER TABLE pagos ADD COLUMN metodo_pago TEXT;")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pagos_venta ON pagos(id_venta);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_pagos_fecha ON pagos(fecha);")
    conexion.commit()

    # --- Recuperacion de contrasena: cada usuario guarda el hash de su
    # codigo de recuperacion (nunca el codigo en texto plano).
    cursor.execute("PRAGMA table_info(usuarios);")
    columnas_usuarios = {fila["name"] for fila in cursor.fetchall()}

    if "codigo_recuperacion_hash" not in columnas_usuarios:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN codigo_recuperacion_hash TEXT;")
        conexion.commit()


if __name__ == "__main__":
    inicializar_base_datos()
    print(f"Base de datos lista en: {RUTA_BASE_DATOS}")
