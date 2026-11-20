import sqlite3
import unittest
from clientes import crear_cliente, actualizar_cliente


def nueva_bd():
    conn = sqlite3.connect(":memory:")
    conn.execute("""CREATE TABLE clientes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL, telefono TEXT, dui TEXT)""")
    return conn


class TestDuplicados(unittest.TestCase):
    def setUp(self):
        self.conn = nueva_bd()
        self.ana = crear_cliente(self.conn, "Ana Pérez", "7000-0001", "01234567-8")

    def test_cliente_nuevo(self):
        crear_cliente(self.conn, "Luis Gómez", "7000-0002", "11111111-1")

    def test_mismo_dui_rechazado(self):
        with self.assertRaises(ValueError):
            crear_cliente(self.conn, "Otra Persona", "7999-9999", "01234567-8")

    def test_mismo_nombre_telefono_sin_mayusculas(self):
        with self.assertRaises(ValueError):
            crear_cliente(self.conn, "ANA PÉREZ", "7000-0001")

    def test_mismo_nombre_distinto_telefono(self):
        crear_cliente(self.conn, "Ana Pérez", "7000-0099")

    def test_editar_sin_cambios(self):
        actualizar_cliente(self.conn, self.ana, "Ana Pérez", "7000-0001", "01234567-8")

    def test_editar_con_dui_de_otro(self):
        luis = crear_cliente(self.conn, "Luis Gómez", "7000-0002", "11111111-1")
        with self.assertRaises(ValueError):
            actualizar_cliente(self.conn, luis, "Luis Gómez", "7000-0002", "01234567-8")

    def test_sin_dui_no_choca_por_dui(self):
        crear_cliente(self.conn, "Sin Dui Uno", "7000-0003")
        crear_cliente(self.conn, "Sin Dui Dos", "7000-0004")


if __name__ == "__main__":
    unittest.main(verbosity=2)
