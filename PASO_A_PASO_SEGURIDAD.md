# Paso a paso: cómo se agregó la seguridad al sistema

Este documento cuenta, **en el orden en que se hizo**, cómo se agregaron al sistema de Tienda Jazmín:

- el cifrado de contraseñas,
- la recuperación de contraseña,
- el bloqueo tras 5 intentos fallidos,
- el historial de inicios de sesión,
- los respaldos automáticos cada 2 días,
- y el último ajuste: mover "Cambiar contraseña" y "Recuperación" a la sección Seguridad.

En cada paso se explica **qué se hizo**, **en qué archivo** y **por qué se hizo así**. Al final hay un resumen corto para exponerlo y respuestas a preguntas frecuentes.

> Para ver cada función con más detalle técnico, consulta `GUIA_SEGURIDAD.md`.

---

## Índice

- [Paso 0. Entender el proyecto antes de tocarlo](#paso-0-entender-el-proyecto-antes-de-tocarlo)
- [Paso 1. Preparar la base de datos](#paso-1-preparar-la-base-de-datos)
- [Paso 2. Herramienta para crear códigos de recuperación](#paso-2-herramienta-para-crear-códigos-de-recuperación)
- [Paso 3. Modelos: hablar con la base de datos](#paso-3-modelos-hablar-con-la-base-de-datos)
- [Paso 4. Módulo de respaldos](#paso-4-módulo-de-respaldos)
- [Paso 5. Controlador de inicio de sesión: las reglas](#paso-5-controlador-de-inicio-de-sesión-las-reglas)
- [Paso 6. Controlador y permiso para la sección Seguridad](#paso-6-controlador-y-permiso-para-la-sección-seguridad)
- [Paso 7. Interfaz: ventanas y pantallas](#paso-7-interfaz-ventanas-y-pantallas)
- [Paso 8. Activar los respaldos automáticos](#paso-8-activar-los-respaldos-automáticos)
- [Paso 9. Pruebas](#paso-9-pruebas)
- [Paso 10. Documentación](#paso-10-documentación)
- [Paso 11. Ajuste: botones dentro de Seguridad](#paso-11-ajuste-botones-dentro-de-seguridad)
- [Paso 12. Ajuste: solo el administrador recupera con código](#paso-12-ajuste-solo-el-administrador-recupera-con-código)
- [Resumen para exponer en 2 minutos](#resumen-para-exponer-en-2-minutos)
- [Preguntas que te pueden hacer](#preguntas-que-te-pueden-hacer)
- [Glosario](#glosario)

---

## Paso 0. Entender el proyecto antes de tocarlo

Antes de escribir código, se revisó cómo estaba hecho el proyecto. Así lo nuevo encaja con lo que ya existía.

**Lo que se encontró:**

1. **El proyecto está organizado en capas.** Así se trabajó todo lo nuevo:

   | Capa | Carpeta | Qué hace | Ejemplo |
   |---|---|---|---|
   | Base de datos | `database/` | Crea las tablas y abre la conexión | `schema.sql`, `conexion.py` |
   | Modelos | `models/` | Consultas SQL: leer y guardar datos | `models/usuario.py` |
   | Controladores | `controllers/` | Reglas del negocio y validaciones | `controlador_login.py` |
   | Interfaz | `ui/` | Ventanas, botones y mensajes (PySide6) | `ui/login_window.py` |
   | Ayudantes | `helpers/` | Funciones de apoyo | `helpers/seguridad.py` |

   La interfaz **nunca** habla directo con la base: le pide las cosas al controlador, el controlador al modelo y el modelo a la base. Gracias a esa separación, las reglas de seguridad quedaron en un solo lugar.

2. **Las contraseñas ya estaban cifradas.** El archivo `helpers/seguridad.py` ya guardaba las contraseñas como *hash* con el algoritmo PBKDF2-SHA256. Ese punto ya estaba resuelto, así que **no se cambió**; se reutilizó la misma función para proteger los códigos de recuperación.

3. **Los formularios tienen una base común.** `ui/widgets/form_dialog.py` (`FormDialog`) ya da el encabezado, los campos, el mensaje de error en rojo y los botones Cancelar/Guardar. Las ventanas nuevas se hicieron heredando de ella, para que se vean igual que el resto del sistema.

4. **Hay dos roles.** `admin` (todas las secciones) y `vendedor` (ventas, créditos, clientes y reportes), definidos en `helpers/permisos.py`.

**Decisión importante:** como el sistema es **100 % local** (sin internet), no se puede recuperar la contraseña por correo. Por eso se eligieron los **códigos de recuperación**, como los "códigos de respaldo" de Google o Microsoft.

---

## Paso 1. Preparar la base de datos

Primero se preparó dónde se iba a guardar la información nueva.

### 1.1 Dos tablas nuevas

Archivo: `database/schema.sql`

**`historial_accesos`**: cada vez que alguien entra, falla, sale o recupera su contraseña se agrega una fila.

| Columna | Qué guarda |
|---|---|
| `fecha` | Día y hora del evento (se llena sola) |
| `usuario` | El nombre de usuario tal como se escribió |
| `id_usuario` | El id de la cuenta, o vacío si ese usuario no existe |
| `evento` | Qué pasó: `inicio`, `fallido`, `bloqueo`, `cierre`, `recuperacion`… |
| `detalle` | Información extra, por ejemplo "Intento 3 de 5" |

**`intentos_login`**: lleva la cuenta de los intentos fallidos para el bloqueo.

| Columna | Qué guarda |
|---|---|
| `usuario` | El nombre escrito, en minúsculas |
| `intentos` | Cuántos intentos fallidos seguidos lleva |
| `bloqueado_hasta` | Hasta qué hora está bloqueado (o vacío) |

Se usó `CREATE TABLE IF NOT EXISTS`: la tabla se crea solo si no existe, así que funciona con bases nuevas y con bases que ya tienen datos.

### 1.2 Una columna nueva en `usuarios`

Archivo: `database/conexion.py`, función `_aplicar_migraciones`

Cada usuario necesitaba un lugar para guardar su código de recuperación (cifrado). Se agregó la columna `codigo_recuperacion_hash`.

No basta con agregarla en `schema.sql`, porque la tabla `usuarios` **ya existe** en las bases que están en uso. Por eso se hizo una **migración**: al arrancar, el programa revisa si la columna existe y, si falta, la agrega:

```python
cursor.execute("PRAGMA table_info(usuarios);")          # lista las columnas actuales
...
if "codigo_recuperacion_hash" not in columnas_usuarios:
    cursor.execute("ALTER TABLE usuarios ADD COLUMN codigo_recuperacion_hash TEXT;")
```

**Resultado:** al actualizar el programa **no se pierde ningún dato** (productos, ventas, clientes…).

---

## Paso 2. Herramienta para crear códigos de recuperación

Archivo: `helpers/seguridad.py`

Se agregaron dos funciones junto a las de cifrado que ya existían:

**`generar_codigo_recuperacion()`** crea un código como `K7QM-3XRA-9TPW`:

- 12 caracteres al azar, en 3 grupos de 4, fáciles de leer y copiar.
- Usa el módulo `secrets`, que genera números aleatorios **seguros**. No se usa `random`, porque es predecible.
- **No usa** `0, O, 1, I, L`, que se confunden al escribirlos a mano.

**`normalizar_codigo(codigo)`** quita los guiones y espacios y pasa todo a mayúsculas. Así da igual si el usuario escribe `k7qm 3xra 9tpw` o `K7QM-3XRA-9TPW`.

---

## Paso 3. Modelos: hablar con la base de datos

Los modelos son las funciones que ejecutan el SQL.

### 3.1 Modelo nuevo: `models/acceso.py`

**Historial:**

| Función | Qué hace |
|---|---|
| `registrar_evento(usuario, evento, id_usuario, detalle)` | Agrega una fila al historial |
| `listar_historial(limite)` | Trae los últimos eventos, junto con el nombre y el rol de la cuenta (`LEFT JOIN usuarios`) |

**Bloqueo:**

| Función | Qué hace |
|---|---|
| `segundos_de_bloqueo(usuario)` | Dice cuántos segundos le faltan al bloqueo. Si el bloqueo ya terminó, borra el registro (el contador vuelve a 0). |
| `registrar_intento_fallido(usuario, max, minutos)` | Suma 1 al contador. Al llegar a 5, guarda "bloqueado hasta ahora + 5 minutos". |
| `limpiar_intentos(usuario)` | Borra el contador cuando el usuario entra bien |

Para sumar 1 se usó un *upsert*: una sola consulta que inserta la fila si no existe o le suma 1 si ya existe.

```sql
INSERT INTO intentos_login (usuario, intentos) VALUES (?, 1)
ON CONFLICT(usuario) DO UPDATE SET intentos = intentos + 1;
```

### 3.2 Funciones nuevas en `models/usuario.py`

- `tiene_codigo_recuperacion(id_usuario)`: ¿ya tiene código?
- `obtener_hash_codigo_recuperacion(id_usuario)`: lee el hash guardado.
- `guardar_codigo_recuperacion(id_usuario, codigo)`: guarda el **hash** del código, nunca el código en texto.

---

## Paso 4. Módulo de respaldos

Archivo nuevo: `database/respaldo.py`

Se hizo un módulo independiente encargado solo de los respaldos.

**Dónde se guardan:** en la carpeta `respaldos/`, al lado de `tienda_jazmin.db`. Cada archivo lleva la fecha en el nombre, por ejemplo `tienda_jazmin_2026-10-11_134810.db`.

**Cómo se crea un respaldo** (`crear_respaldo`):

1. Se crea la carpeta si no existe.
2. Se copia la base con `conexion.backup(...)`, la función **oficial de SQLite** para respaldos. Una copia normal de archivo podría quedar dañada si el programa está escribiendo en ese momento; `backup()` siempre produce una copia correcta.
3. La copia se escribe primero como `.tmp` y se renombra al terminar. Si se corta la luz a la mitad, no queda un respaldo roto que parezca bueno.
4. Se borran los más viejos y solo se conservan los **15 más recientes**, para no llenar el disco.

**Cuándo toca un respaldo** (`respaldo_automatico_si_toca`): si no hay ninguno, o si el último tiene **2 días o más**, crea uno. Si no, no hace nada.

La fecha del último respaldo se lee del **nombre** del archivo y no de la fecha de modificación, porque OneDrive u otros programas pueden cambiar esa fecha.

---

## Paso 5. Controlador de inicio de sesión: las reglas

Archivo: `controllers/controlador_login.py`

Aquí está la lógica principal. Se modificó la función que ya existía y se agregaron otras.

### 5.1 Configuración

```python
MAX_INTENTOS = 5        # intentos antes del bloqueo
MINUTOS_BLOQUEO = 5     # duración del bloqueo
```

### 5.2 `iniciar_sesion(usuario, password)`, ahora con bloqueo e historial

Pasos que sigue cuando alguien pulsa "Iniciar sesión":

1. ¿Escribió usuario y contraseña? Si no, avisa.
2. **¿Está bloqueado?** Si sí, no revisa la contraseña. Registra `intento_bloqueado` y responde *"Intenta de nuevo en X minutos"*.
3. ¿El usuario existe y la contraseña es correcta?
   - **No** → llama a `_registrar_fallo`, que:
     - suma 1 intento y registra `fallido` en el historial;
     - si llegó a 5, bloquea y registra `bloqueo`;
     - si le quedan 2 o 1, agrega el aviso *"Te quedan N intentos"*.
   - **Sí** → borra los intentos, registra `inicio` y guarda la sesión.

**Detalle de seguridad:** el mensaje de error siempre es el mismo (*"Usuario o contraseña incorrectos"*), y también se bloquean los usuarios que **no existen**. Así, quien intente adivinar no puede saber qué usuarios son reales.

### 5.3 `cerrar_sesion()`

Registra el evento `cierre` y limpia la sesión.

### 5.4 Funciones del código de recuperación

| Función | Qué hace |
|---|---|
| `asegurar_codigo_recuperacion()` | Después de entrar, si el usuario no tiene código, lo crea y lo devuelve para mostrarlo **una vez** |
| `regenerar_codigo_recuperacion(password)` | Pide la contraseña y crea un código nuevo; el anterior deja de servir |
| `recuperar_password(usuario, codigo, nueva, confirmacion)` | Cambia la contraseña usando el código (ver abajo) |

**Cómo funciona `recuperar_password`:**

1. Revisa que los campos estén completos y que la contraseña nueva tenga 6 caracteres o más y coincida con la confirmación.
2. Revisa si el usuario está bloqueado. **La recuperación también respeta el bloqueo**; si no, alguien podría usarla para seguir adivinando.
3. Compara el código con el hash guardado.
4. Si falla, cuenta como intento fallido (con las mismas reglas del paso 5.2).
5. Si es correcto:
   - guarda la nueva contraseña (cifrada);
   - crea **un código nuevo**, porque el usado ya no sirve (es de un solo uso);
   - borra los intentos fallidos;
   - registra `recuperacion` en el historial.

---

## Paso 6. Controlador y permiso para la sección Seguridad

**Controlador nuevo:** `controllers/controlador_seguridad.py`. Le da los datos a la pantalla Seguridad:

- `obtener_historial_accesos()`: el historial (solo si quien pregunta es administrador).
- `obtener_estado_respaldos()`: último respaldo, próximo, cantidad y carpeta.
- `crear_respaldo_manual()`: para el botón "Crear respaldo ahora".

**Permiso:** en `helpers/permisos.py` se agregó `"seguridad"` a las secciones del rol `admin`. Así **solo el administrador** ve esa sección en el menú.

---

## Paso 7. Interfaz: ventanas y pantallas

Con la lógica lista, se hizo la parte visual.

### 7.1 Íconos nuevos

Archivo: `ui/icons.py`. Se agregaron `key` (llave), `shield` (escudo), `folder` (carpeta), `copy` (copiar) y `database` (base de datos). Están dibujados en SVG, como los demás íconos del sistema.

### 7.2 Ventanas de recuperación

Archivo nuevo: `ui/dialogs/recuperacion_dialog.py`. Tiene tres ventanas, todas basadas en `FormDialog`:

| Ventana | Cuándo aparece | Qué muestra |
|---|---|---|
| `CodigoRecuperacionDialog` | Al recibir un código | El código en letras grandes, el botón "Copiar código", el aviso de guardarlo y el botón "Ya lo guardé" |
| `RecuperarPasswordDialog` | "¿Olvidaste tu contraseña?" | Campos: usuario, código, nueva contraseña y confirmación |
| `NuevoCodigoDialog` | Al pedir un código nuevo | Pide la contraseña actual |

Las ventanas **no deciden nada**: recogen los datos, llaman al controlador y muestran el resultado. Si hay error, lo muestran en rojo y marcan el campo con problema.

### 7.3 Ventana de inicio de sesión

Archivo: `ui/login_window.py`

- Se agregó el enlace **"¿Olvidaste tu contraseña?"** debajo del botón "Iniciar sesión".
- Después de entrar correctamente, si el usuario no tiene código, aparece la ventana con su código **antes** de abrir el sistema.
- Al terminar una recuperación, se muestra el código nuevo y se vuelve al inicio de sesión con el usuario ya escrito.

### 7.4 Ventana principal

Archivo: `ui/main_window.py`

- Se agregó la sección **Seguridad** al menú lateral.
- Se movió el registro del cierre de sesión a `closeEvent`, que se ejecuta **siempre** que la ventana se cierra: tanto con "Cerrar sesión" como con la X. Así ningún cierre se queda sin registrar.

### 7.5 Pantalla Seguridad

Archivo nuevo: `ui/pages/seguridad.py`. Se hizo como las demás pantallas: hereda de `Page` y tiene un método `refresh()` que recarga los datos cada vez que se entra.

- **Tarjeta Respaldos:** último respaldo, próximo automático, cantidad y carpeta, con los botones "Crear respaldo ahora" y "Abrir carpeta".
- **Tarjeta Historial:**
  - tabla con fecha, usuario, cuenta, evento (etiqueta de color) y detalle;
  - filtro por tipo de evento y buscador;
  - resumen al pie.

---

## Paso 8. Activar los respaldos automáticos

El módulo del paso 4 no hace nada si nadie lo llama. Se conectó en **dos lugares**:

1. **Al abrir el programa** (`main.py`): justo después de preparar la base, se llama a `respaldo_automatico_si_toca()`.
2. **Cada hora mientras está abierto** (`ui/app.py`): un `QTimer` (temporizador de Qt) vuelve a revisar cada hora. Esto cubre el caso de una computadora que se queda encendida varios días con el programa abierto.

Ambos están dentro de un `try/except`: si un respaldo falla (por ejemplo, por disco lleno), **el programa sigue funcionando**. Un respaldo fallido nunca debe impedir vender.

---

## Paso 9. Pruebas

Para no arriesgar los datos reales, **las pruebas se hicieron sobre una copia** de `tienda_jazmin.db`, en una carpeta temporal.

**Prueba de la lógica** (un script que llama directamente a los controladores):

| Se probó | Resultado esperado | ¿Pasó? |
|---|---|---|
| Respaldo automático la primera vez | Crea uno | ✔ |
| Respaldo automático otra vez el mismo día | No crea otro | ✔ |
| Entrar por primera vez | Entrega un código de recuperación | ✔ |
| Entrar por segunda vez | No entrega código (ya tiene) | ✔ |
| 5 contraseñas incorrectas (mezclando `prueba` y `PRUEBA`) | Avisos en el 3.º y 4.º; bloqueo en el 5.º | ✔ |
| Contraseña correcta durante el bloqueo | Rechazada, con el tiempo restante | ✔ |
| Recuperar durante el bloqueo | Rechazado | ✔ |
| Código incorrecto | Rechazado | ✔ |
| Código en minúsculas y con espacios | Aceptado | ✔ |
| Reusar un código ya usado | Rechazado | ✔ |
| Entrar con la contraseña recuperada | Funciona | ✔ |
| Usuario que no existe | Mensaje genérico | ✔ |
| Historial | Todos los eventos registrados en orden | ✔ |

**Prueba de la interfaz:** se abrieron las ventanas sin mostrarlas en pantalla (modo *offscreen*) y se comprobó que:

- el error se muestra dentro de la ventana de recuperación;
- la pantalla Seguridad carga el historial y el filtro funciona;
- "Crear respaldo ahora" crea un respaldo;
- al cerrar la ventana principal se registra el cierre de sesión.

---

## Paso 10. Documentación

- `README.md`: se agregó la sección Seguridad y las nuevas funciones.
- `GUIA_SEGURIDAD.md`: explicación de cada función (interfaz y código).
- `.gitignore`: se agregó la carpeta `respaldos/`, para que las copias de la base no se suban a Git.

---

## Paso 11. Ajuste: botones dentro de Seguridad

Después se pidió que **"Cambiar contraseña" y "Recuperación" estuvieran en la sección Seguridad**.

**Lo que se hizo:**

1. **`ui/pages/seguridad.py`:** se agregó arriba una tarjeta nueva, **"Contraseñas y recuperación"**, con los botones **"Cambiar contraseña"** y **"Nuevo código"**.
2. **`ui/widgets/topbar.py`:** se quitaron esos botones de la barra superior del administrador.
   - **Excepción:** la cuenta de **ventas** conserva el botón "Recuperación" en la barra, porque no tiene la sección Seguridad. Si se le quitaba, no tendría forma de generar su código.
3. **`ui/main_window.py`:** las funciones que abren esas ventanas pasaron a ser públicas (`cambiar_password()` y `nuevo_codigo_recuperacion()`). Así las usan tanto la pantalla Seguridad como la barra de ventas, **sin repetir código**.
4. **`controllers/controlador_usuarios.py`:** cada cambio de contraseña ahora se registra en el historial como **"Contraseña cambiada"**, indicando quién la cambió.
5. Después de usar cualquiera de los dos botones, la pantalla Seguridad se recarga y el nuevo evento aparece en el historial.

**Pruebas del ajuste:**

- la barra del administrador solo muestra "Cerrar sesión";
- la de ventas muestra "Recuperación" y "Cerrar sesión";
- los botones de Seguridad abren sus ventanas;
- el cambio de contraseña aparece en el historial.

---

## Paso 12. Ajuste: solo el administrador recupera con código

Después se pidió **quitar la recuperación de contraseña al rol de ventas**, pero que el administrador siempre pudiera cambiar y recuperar las contraseñas.

**Lo que se hizo:**

1. **`controllers/controlador_login.py`:**
   - Se agregó `ROLES_CON_RECUPERACION = ("admin",)` y la función `_puede_recuperar(rol)`.
   - `asegurar_codigo_recuperacion()` ya no crea código para ventas: a esa cuenta no se le muestra nada al entrar.
   - `regenerar_codigo_recuperacion()` rechaza a las cuentas de ventas.
   - `recuperar_password()` trata a una cuenta de ventas igual que un código incorrecto. Usa el **mismo mensaje** (que sugiere pedir el cambio al administrador) para no revelar qué tipo de cuenta es cada usuario, y cuenta como intento fallido para el bloqueo.
2. **`database/conexion.py`:** una migración borra los códigos que las cuentas de ventas pudieran tener de la versión anterior, para que ya no sirvan.
3. **`ui/widgets/topbar.py` y `ui/main_window.py`:** se quitó el botón "Recuperación" de la barra superior de ventas. Ahora la barra solo tiene "Cerrar sesión" para todos, y `nuevo_codigo_recuperacion()` comprueba que la sesión sea de administrador.
4. **`ui/dialogs/recuperacion_dialog.py`:** el texto de ayuda aclara que el código es solo para el administrador.

**Lo que sigue igual para el administrador:**

- recibe su código al entrar por primera vez;
- recupera su propia contraseña con "¿Olvidaste tu contraseña?";
- genera un código nuevo desde **Seguridad → Nuevo código**;
- cambia su contraseña o **restablece la de ventas** desde **Seguridad → Cambiar contraseña**.

**Pruebas (sobre una copia de la base):**

| Se probó | Resultado |
|---|---|
| Ventas tenía un código de la versión anterior | La migración lo borró ✔ |
| Ventas inicia sesión | No recibe código ✔ |
| Ventas intenta generar un código | Rechazado ✔ |
| Ventas intenta recuperar con su código viejo | Rechazado, con el mensaje genérico ✔ |
| Admin recupera su contraseña con su código | Funciona y recibe un código nuevo ✔ |
| Admin cambia la contraseña de ventas | Funciona y ventas entra con la nueva ✔ |
| Barra superior de admin y de ventas | Solo "Cerrar sesión" ✔ |

---

## Resumen para exponer en 2 minutos

> "El sistema ya guardaba las contraseñas cifradas con PBKDF2-SHA256, que es un hash con sal y miles de iteraciones, así que nunca se guardan en texto.
>
> Como el sistema es local y no usa correo, para **recuperar la contraseña** el administrador recibe un **código de recuperación** la primera vez que entra. Si olvida la contraseña, pone su usuario, el código y la nueva contraseña. Las cuentas de ventas no tienen código: si olvidan su contraseña, el administrador se la cambia. El código es de un solo uso y también se guarda cifrado.
>
> Para evitar ataques de **fuerza bruta**, después de **5 intentos fallidos** el usuario se **bloquea 5 minutos**, incluso si después escribe la contraseña correcta. La recuperación también cuenta como intento.
>
> Todo queda en un **historial de accesos**: inicios, cierres, fallos, bloqueos, recuperaciones y cambios de contraseña. El administrador lo ve en la sección **Seguridad**, donde también puede cambiar contraseñas y generar códigos.
>
> Además, cada **2 días** el sistema crea solo un **respaldo** de la base de datos, usando la función oficial de SQLite, y conserva los 15 más recientes.
>
> Lo organizamos en capas: la base de datos, los modelos con el SQL, los controladores con las reglas y la interfaz con PySide6."

---

## Preguntas que te pueden hacer

**¿Por qué no se recupera la contraseña por correo?**
Porque el sistema funciona sin internet. El código de recuperación funciona igual que los "códigos de respaldo" de Google o Microsoft.

**¿Qué es un hash y por qué no se guarda la contraseña tal cual?**
Un hash es el resultado de pasar la contraseña por una función de un solo sentido: con el hash no se puede volver a obtener la contraseña. Si alguien copia la base de datos, no puede leer las contraseñas.

**¿Para qué sirve la "sal"?**
Es un valor aleatorio distinto para cada contraseña. Hace que dos usuarios con la misma contraseña tengan hashes diferentes e impide usar listas de hashes ya calculados.

**¿Por qué 260 000 iteraciones?**
Para que calcular cada hash sea lento a propósito. Para un usuario normal no se nota, pero para quien intente millones de combinaciones se vuelve muy costoso.

**¿Por qué también se bloquean usuarios que no existen?**
Si solo se bloquearan los reales, un atacante podría descubrir qué usuarios existen viendo cuáles se bloquean.

**¿Qué pasa si un usuario pierde su código?**
- Las cuentas de **ventas** no tienen código: el administrador les cambia la contraseña desde Seguridad.
- Si es el **administrador**, puede generar un código nuevo mientras recuerde su contraseña. Por eso es importante guardar el código en un lugar seguro.

**¿Por qué el código es de un solo uso?**
Si alguien llegara a verlo, solo serviría una vez. Además, al usarlo, el sistema entrega uno nuevo.

**¿Por qué se usa `backup()` de SQLite y no se copia el archivo?**
Porque si el programa está escribiendo justo al copiar, la copia podría quedar dañada. `backup()` siempre produce una copia correcta.

**¿Dónde están los respaldos y cómo se restauran?**
En la carpeta `respaldos/`, junto a la base; se abre con el botón "Abrir carpeta". Para restaurar: cerrar el programa, copiar el respaldo deseado sobre `tienda_jazmin.db` y volver a abrir.

**¿Se pierden datos al actualizar el programa?**
No. Las tablas nuevas se crean solo si no existen, y la columna nueva se agrega con una migración que no toca los datos existentes.

---

## Glosario

| Término | Significado |
|---|---|
| **Hash** | "Huella" de un texto que no se puede revertir; se usa para guardar contraseñas |
| **PBKDF2-SHA256** | Algoritmo estándar para convertir contraseñas en hash de forma lenta y segura |
| **Sal** | Valor aleatorio que se mezcla con la contraseña antes de hacer el hash |
| **Fuerza bruta** | Ataque que prueba muchas contraseñas hasta acertar |
| **Migración** | Cambio en la estructura de la base de datos que se aplica sin perder datos |
| **Upsert** | Consulta que inserta una fila o la actualiza si ya existe |
| **Modelo** | Código que ejecuta las consultas SQL |
| **Controlador** | Código con las reglas y validaciones |
| **Respaldo (backup)** | Copia de seguridad de la base de datos |
| **`QTimer`** | Temporizador de Qt que ejecuta una función cada cierto tiempo |
| **Offscreen** | Modo de prueba que abre las ventanas sin mostrarlas en pantalla |
