# Tienda Jazmín — Sistema de inventario y ventas

Aplicación de escritorio para administrar el inventario, las ventas, los créditos a clientes y los reportes de una tienda. Está hecha en Python con **PySide6** (Qt) para la interfaz, **SQLite** como base de datos y **ReportLab** para generar PDF.

## Funcionalidades

| Sección | Qué permite hacer |
|---|---|
| **Inicio** | Resumen del día: productos activos, ventas de hoy, dinero recibido, crédito pendiente, stock bajo y últimas ventas |
| **Reportes** | Reportes diarios, semanales, mensuales y anuales con gráficos, comparación con el período anterior y exportación a PDF |
| **Ventas** | Registro de ventas al contado (efectivo, tarjeta u otro) o a crédito, con descuento automático del inventario |
| **Créditos** | Cuentas por cobrar: pagos parciales o totales, estado calculado (Pendiente / Parcial / Pagado), saldo por cliente y comprobante en PDF |
| **Inventario** | Entradas y salidas manuales, historial de movimientos y alertas de stock bajo |
| **Productos** | Alta, edición y activación/desactivación de productos con precios, existencia y stock mínimo |
| **Categorías** | Gestión de categorías de productos |
| **Clientes** | Registro de clientes con límite de crédito opcional |
| **Seguridad** | (solo administrador) Cambiar contraseñas, generar código de recuperación, historial de accesos y respaldos de la base de datos |

Además:

- Inicio de sesión con contraseñas cifradas (PBKDF2-SHA256) y dos cuentas con funciones separadas:

  | Cuenta | Rol | Secciones. |
  |---|---|---|
  | Administrador | `admin` | Todas las secciones: Inicio, Reportes, Ventas, Créditos, Clientes, Inventario, Productos, Categorías y Seguridad |
  | Ventas | `vendedor` | Reportes, Ventas, Créditos y Clientes |

  Cada cuenta solo ve en el menú las secciones de su rol (ver `helpers/permisos.py`).
- El administrador puede cambiar su contraseña y la de la cuenta de ventas desde **Seguridad → Cambiar contraseña** (pide la contraseña actual del administrador). Cada cambio queda en el historial de accesos.
- **Recuperación de contraseña sin internet**: al iniciar sesión por primera vez cada usuario recibe un *código de recuperación* (se muestra una sola vez y en la base solo se guarda su hash). Si olvida la contraseña, en **¿Olvidaste tu contraseña?** escribe su usuario, el código y la nueva contraseña. El código es de un solo uso: al usarlo se entrega uno nuevo. Con la sesión iniciada se puede generar otro: el administrador desde **Seguridad → Nuevo código** y la cuenta de ventas desde el botón **Recuperación** de la barra superior.
- **Bloqueo temporal contra fuerza bruta**: tras 5 intentos fallidos seguidos (de inicio de sesión o de recuperación) el usuario queda bloqueado 5 minutos (`MAX_INTENTOS` y `MINUTOS_BLOQUEO` en `controllers/controlador_login.py`).
- **Historial de accesos**: se registran inicios y cierres de sesión, intentos fallidos, bloqueos y recuperaciones de contraseña (sección **Seguridad**).
- **Respaldos automáticos cada 2 días** en la carpeta `respaldos/` junto a `tienda_jazmin.db` (o junto al `.exe`). Se revisa al abrir el programa y cada hora mientras está abierto; se conservan los 15 más recientes. También se puede crear uno al momento desde **Seguridad**. Para restaurar, cerrar el programa y copiar el respaldo sobre `tienda_jazmin.db`.
- Búsqueda en todas las tablas sin importar mayúsculas ni tildes.
- Las consultas pesadas y la generación de PDF se ejecutan en segundo plano para no congelar la interfaz.

## Requisitos

- Python 3.10 o superior (probado con 3.13)
- Windows recomendado (el acceso directo y el icono de la barra de tareas son específicos de Windows), aunque la aplicación funciona en cualquier sistema compatible con PySide6.

## Instalación

Con `pip`:

```bash
python -m venv .venv
.venv\Scripts\activate          # En Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

O con [uv](https://docs.astral.sh/uv/):

```bash
uv venv --python 3.13
uv pip install --python .venv -r requirements.txt
```

## Ejecución

```bash
python main.py
```

Al abrir el sistema por primera vez:

1. Se crea la base de datos `database/tienda_jazmin.db` a partir de `database/schema.sql` (y se aplican las migraciones pendientes).
2. Si falta alguna de las dos cuentas, se crea con estos datos por defecto:

   | Usuario | Contraseña |
   |---|---|
   | `admin` | `admin123` |
   | `ventas` | `ventas123` |

   **Cambia ambas contraseñas (sesión de administrador → Seguridad → Cambiar contraseña) antes de usar el sistema en producción.**

### Acceso directo en el escritorio (Windows)

Con el entorno `.venv` ya creado, ejecuta desde la carpeta del proyecto:

```powershell
powershell -ExecutionPolicy Bypass -File .\crear_acceso_directo.ps1
```

Se crea el acceso **Tienda Jazmín** en el escritorio, que abre el programa sin ventana de consola. Si mueves la carpeta del proyecto, vuelve a ejecutar el script.

## Atajos de teclado

| Atajo | Acción |
|---|---|
| `Ctrl+1`, `Ctrl+2`… | Cambiar de sección (en el orden del menú lateral) |
| `F5` | Recargar los datos de la pantalla actual |
| `Ctrl+Enter` | Guardar en los formularios |
| Doble clic en una fila | Editar el registro o abrir su detalle |

## Estructura del proyecto

```
├── main.py                 Punto de entrada
├── requirements.txt
├── crear_acceso_directo.ps1
├── tienda_jazmin.ico
├── database/               Conexión SQLite, esquema y migraciones
├── models/                 Acceso a datos (consultas SQL)
├── controllers/            Lógica de negocio y validaciones
├── helpers/                Formato, seguridad (hash de contraseñas) y sesión
├── reportes/               Períodos, resúmenes y generación de PDF
├── ui/                     Interfaz PySide6
│   ├── app.py              Arranque: login → ventana principal → cerrar sesión
│   ├── main_window.py      Barra superior, menú lateral y pantallas
│   ├── theme.py            Colores y tamaños
│   ├── styles/theme.qss    Estilos visuales
│   ├── pages/              Una pantalla por sección
│   ├── dialogs/            Formularios modales
│   └── widgets/            Componentes reutilizables (tablas, gráficos, avisos…)
└── views/                  Interfaz anterior en Tkinter (ya no se usa)
```

La aplicación sigue una separación en capas: **ui → controllers → models → database**. La interfaz nunca consulta la base de datos directamente.

## Base de datos

- Motor: SQLite 3, archivo `database/tienda_jazmin.db`.
- Tablas principales: `usuarios`, `categorias`, `productos`, `clientes`, `proveedores`, `ventas`, `detalle_ventas`, `compras`, `detalle_compras`, `pagos`, `movimientos_cuenta_cliente`, `movimientos_inventario`, `historial_accesos` e `intentos_login`.
- **Todos los montos se guardan como enteros en centavos** (por ejemplo, $17.50 se guarda como `1750`) para evitar errores de redondeo.
- Las migraciones se aplican automáticamente al iniciar (`database/conexion.py`).
- El saldo, lo pagado y el estado de cada crédito no se guardan: se calculan siempre a partir de los pagos registrados.

Para crear o actualizar la base de datos sin abrir la interfaz:

```bash
python -m database.conexion
```

## Documentación adicional

[CAMBIOS_INTERFAZ.md](CAMBIOS_INTERFAZ.md) describe con más detalle la migración de Tkinter a PySide6, el módulo de reportes (de dónde sale cada dato) y el funcionamiento de los créditos.

[GUIA_SEGURIDAD.md](GUIA_SEGURIDAD.md) explica la recuperación de contraseña, el bloqueo por intentos fallidos, el historial de accesos y los respaldos automáticos (interfaz y código).  
