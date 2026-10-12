-- ============================================================
-- ESQUEMA DE BASE DE DATOS - TIENDA JAZMIN
-- Motor: SQLite 3
-- ============================================================
-- NOTA IMPORTANTE: todos los montos de dinero se guardan como
-- INTEGER en CENTAVOS (ej. $17.50 se guarda como 1750).
-- Esto evita errores de redondeo con decimales binarios.
-- Al mostrar en pantalla, dividir entre 100.
-- ============================================================

-- Activar el respeto a las llaves foraneas (SQLite las ignora
-- por defecto si no se activa esto en cada conexion).
PRAGMA foreign_keys = ON;

-- ------------------------------------------------------------
-- USUARIOS
-- Quienes operan el sistema (administradores y vendedores)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS usuarios (
    id_usuario      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    usuario         TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,          -- guardado con password_hash de Python (ver Etapa 6)
    rol             TEXT NOT NULL CHECK(rol IN ('admin', 'vendedor')),
    estado          INTEGER NOT NULL DEFAULT 1 CHECK(estado IN (0, 1)),  -- 1 = activo, 0 = inactivo
    fecha_registro  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ------------------------------------------------------------
-- CATEGORIAS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS categorias (
    id_categoria    INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    estado          INTEGER NOT NULL DEFAULT 1 CHECK(estado IN (0, 1))
);

-- ------------------------------------------------------------
-- PRODUCTOS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS productos (
    id_producto     INTEGER PRIMARY KEY AUTOINCREMENT,
    codigo          TEXT NOT NULL UNIQUE,
    nombre          TEXT NOT NULL,
    descripcion     TEXT,
    id_categoria    INTEGER NOT NULL,
    precio_compra   INTEGER NOT NULL CHECK(precio_compra >= 0),  -- en centavos
    precio_venta    INTEGER NOT NULL CHECK(precio_venta >= 0),   -- en centavos
    existencia      INTEGER NOT NULL DEFAULT 0 CHECK(existencia >= 0),
    stock_minimo    INTEGER NOT NULL DEFAULT 0 CHECK(stock_minimo >= 0),
    unidad_medida   TEXT NOT NULL DEFAULT 'unidad',
    estado          INTEGER NOT NULL DEFAULT 1 CHECK(estado IN (0, 1)),
    FOREIGN KEY (id_categoria) REFERENCES categorias(id_categoria)
);

-- ------------------------------------------------------------
-- CLIENTES
-- Solo nombre y telefono son obligatorios (ver analisis previo)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS clientes (
    id_cliente      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre_completo TEXT NOT NULL,
    telefono        TEXT NOT NULL,
    dui             TEXT,                   -- opcional
    direccion       TEXT,                   -- opcional
    correo          TEXT,                   -- opcional
    limite_credito  INTEGER,                -- en centavos; NULL = sin limite (ver Etapa 11)
    estado          INTEGER NOT NULL DEFAULT 1 CHECK(estado IN (0, 1)),
    fecha_registro  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- ------------------------------------------------------------
-- PROVEEDORES
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS proveedores (
    id_proveedor    INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre          TEXT NOT NULL,
    telefono        TEXT,
    direccion       TEXT,
    correo          TEXT,
    estado          INTEGER NOT NULL DEFAULT 1 CHECK(estado IN (0, 1))
);

-- ------------------------------------------------------------
-- VENTAS (cabecera)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS ventas (
    id_venta        INTEGER PRIMARY KEY AUTOINCREMENT,
    numero_venta    TEXT NOT NULL UNIQUE,
    fecha           TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    id_cliente      INTEGER,                -- NULL si es venta al contado sin cliente registrado
    id_usuario      INTEGER NOT NULL,
    tipo_pago       TEXT NOT NULL CHECK(tipo_pago IN ('efectivo', 'tarjeta', 'otro', 'credito')),
    subtotal        INTEGER NOT NULL CHECK(subtotal >= 0),  -- centavos
    total           INTEGER NOT NULL CHECK(total >= 0),     -- centavos
    estado          INTEGER NOT NULL DEFAULT 1 CHECK(estado IN (0, 1)),  -- 0 = anulada
    FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);

-- ------------------------------------------------------------
-- DETALLE_VENTAS (lineas de productos dentro de una venta)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS detalle_ventas (
    id_detalle      INTEGER PRIMARY KEY AUTOINCREMENT,
    id_venta        INTEGER NOT NULL,
    id_producto     INTEGER NOT NULL,
    cantidad        INTEGER NOT NULL CHECK(cantidad > 0),
    precio_unitario INTEGER NOT NULL CHECK(precio_unitario >= 0),  -- centavos, copiado al momento de vender
    subtotal        INTEGER NOT NULL CHECK(subtotal >= 0),         -- centavos
    FOREIGN KEY (id_venta) REFERENCES ventas(id_venta),
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
);

-- ------------------------------------------------------------
-- COMPRAS (cabecera - entradas de inventario)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS compras (
    id_compra       INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha           TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    id_proveedor    INTEGER NOT NULL,
    id_usuario      INTEGER NOT NULL,
    total           INTEGER NOT NULL CHECK(total >= 0),  -- centavos
    FOREIGN KEY (id_proveedor) REFERENCES proveedores(id_proveedor),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);

-- ------------------------------------------------------------
-- DETALLE_COMPRAS
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS detalle_compras (
    id_detalle_compra INTEGER PRIMARY KEY AUTOINCREMENT,
    id_compra         INTEGER NOT NULL,
    id_producto       INTEGER NOT NULL,
    cantidad          INTEGER NOT NULL CHECK(cantidad > 0),
    precio_unitario   INTEGER NOT NULL CHECK(precio_unitario >= 0),  -- centavos
    subtotal          INTEGER NOT NULL CHECK(subtotal >= 0),         -- centavos
    FOREIGN KEY (id_compra) REFERENCES compras(id_compra),
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto)
);

-- ------------------------------------------------------------
-- PAGOS (abonos que un cliente hace contra su deuda)
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS pagos (
    id_pago         INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente      INTEGER NOT NULL,
    fecha           TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    monto           INTEGER NOT NULL CHECK(monto > 0),  -- centavos
    id_usuario      INTEGER NOT NULL,       -- quien recibio el pago
    observacion     TEXT,
    saldo_anterior  INTEGER NOT NULL,       -- centavos
    saldo_nuevo     INTEGER NOT NULL,       -- centavos
    FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente),
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);

-- ------------------------------------------------------------
-- MOVIMIENTOS_CUENTA_CLIENTE
-- Historial completo de cargos (ventas a credito) y abonos (pagos).
-- Esta tabla es la que permite reconstruir de donde salio cada
-- peso de deuda, tal como se pidio en el analisis original.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS movimientos_cuenta_cliente (
    id_movimiento   INTEGER PRIMARY KEY AUTOINCREMENT,
    id_cliente      INTEGER NOT NULL,
    tipo            TEXT NOT NULL CHECK(tipo IN ('cargo', 'abono')),
    id_venta        INTEGER,                -- se llena si tipo = 'cargo'
    id_pago         INTEGER,                -- se llena si tipo = 'abono'
    monto           INTEGER NOT NULL CHECK(monto > 0),  -- centavos
    saldo_anterior  INTEGER NOT NULL,       -- centavos
    saldo_nuevo     INTEGER NOT NULL,       -- centavos
    fecha           TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    descripcion     TEXT,
    FOREIGN KEY (id_cliente) REFERENCES clientes(id_cliente),
    FOREIGN KEY (id_venta) REFERENCES ventas(id_venta),
    FOREIGN KEY (id_pago) REFERENCES pagos(id_pago)
);

-- ------------------------------------------------------------
-- MOVIMIENTOS_INVENTARIO
-- Historial de cada entrada/salida de stock, para poder
-- auditar por que cambio la existencia de un producto.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS movimientos_inventario (
    id_movimiento       INTEGER PRIMARY KEY AUTOINCREMENT,
    id_producto         INTEGER NOT NULL,
    tipo                TEXT NOT NULL CHECK(tipo IN ('entrada', 'salida', 'ajuste')),
    cantidad            INTEGER NOT NULL CHECK(cantidad > 0),
    existencia_anterior INTEGER NOT NULL,
    existencia_nueva    INTEGER NOT NULL,
    id_venta            INTEGER,            -- se llena si tipo = 'salida' por venta
    id_compra           INTEGER,            -- se llena si tipo = 'entrada' por compra
    descripcion         TEXT,               -- motivo, usado sobre todo en ajustes manuales
    fecha               TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (id_producto) REFERENCES productos(id_producto),
    FOREIGN KEY (id_venta) REFERENCES ventas(id_venta),
    FOREIGN KEY (id_compra) REFERENCES compras(id_compra)
);

-- ------------------------------------------------------------
-- INDICES
-- Aceleran las busquedas mas frecuentes del sistema.
-- ------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_productos_categoria ON productos(id_categoria);
CREATE INDEX IF NOT EXISTS idx_ventas_cliente ON ventas(id_cliente);
CREATE INDEX IF NOT EXISTS idx_ventas_fecha ON ventas(fecha);
CREATE INDEX IF NOT EXISTS idx_detalle_ventas_venta ON detalle_ventas(id_venta);
CREATE INDEX IF NOT EXISTS idx_movimientos_cuenta_cliente ON movimientos_cuenta_cliente(id_cliente);
CREATE INDEX IF NOT EXISTS idx_movimientos_inventario_producto ON movimientos_inventario(id_producto);

-- ------------------------------------------------------------
-- HISTORIAL_ACCESOS
-- Registro de inicios de sesion (exitosos y fallidos), cierres,
-- bloqueos y recuperaciones de contrasena. Lo consulta el
-- administrador en la seccion "Seguridad".
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS historial_accesos (
    id_acceso       INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha           TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    usuario         TEXT NOT NULL,          -- login tal como se escribio
    id_usuario      INTEGER,                -- NULL si el usuario no existe
    evento          TEXT NOT NULL,          -- inicio, fallido, bloqueo, cierre, recuperacion...
    detalle         TEXT,
    FOREIGN KEY (id_usuario) REFERENCES usuarios(id_usuario)
);

CREATE INDEX IF NOT EXISTS idx_historial_accesos_fecha ON historial_accesos(fecha);

-- ------------------------------------------------------------
-- INTENTOS_LOGIN
-- Intentos fallidos seguidos por nombre de usuario, para el
-- bloqueo temporal contra fuerza bruta. Se lleva por el texto
-- escrito (en minusculas), exista o no la cuenta, para no
-- revelar que usuarios existen.
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS intentos_login (
    usuario         TEXT PRIMARY KEY,
    intentos        INTEGER NOT NULL DEFAULT 0,
    bloqueado_hasta TEXT                    -- 'YYYY-MM-DD HH:MM:SS' local, NULL = sin bloqueo
);
