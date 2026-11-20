-- Opcional: refuerzo en la base de datos. Limpia duplicados existentes antes de ejecutarlo.
CREATE UNIQUE INDEX IF NOT EXISTS ux_clientes_dui
ON clientes(dui) WHERE dui IS NOT NULL AND dui <> '';
