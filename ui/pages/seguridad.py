"""
Pantalla de Seguridad (solo administrador).

- Contrasenas y recuperacion: cambiar la contrasena (propia o de ventas)
  y generar un nuevo codigo de recuperacion. Los dialogos los abre la
  ventana principal (cambiar_password / nuevo_codigo_recuperacion).
- Respaldos: cuando fue el ultimo, cuando toca el siguiente automatico
  (cada 2 dias), boton para respaldar ahora y abrir la carpeta.
- Historial de accesos: inicios y cierres de sesion, intentos fallidos,
  bloqueos temporales y recuperaciones de contrasena.

Usa: controlador_seguridad.
"""

import os

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QVBoxLayout

from controllers import controlador_seguridad
from ui.formato_ui import fecha_corta, plural
from ui.widgets import messages
from ui.widgets.common import Card, button, label
from ui.widgets.data_table import Column, DataTable
from ui.widgets.forms import SearchField, choice_combo
from ui.widgets.page import Page

_EVENTOS = {
    "inicio": ("Inicio de sesión", "success"),
    "cierre": ("Cierre de sesión", "neutral"),
    "fallido": ("Intento fallido", "warning"),
    "bloqueo": ("Usuario bloqueado", "danger"),
    "intento_bloqueado": ("Intento bloqueado", "danger"),
    "recuperacion": ("Contraseña recuperada", "info"),
    "recuperacion_fallida": ("Recuperación fallida", "warning"),
    "codigo_generado": ("Código generado", "info"),
    "cambio_password": ("Contraseña cambiada", "info"),
}

_FILTROS = [
    ("Todos los eventos", None),
    ("Inicios y cierres", {"inicio", "cierre"}),
    ("Intentos fallidos", {"fallido", "recuperacion_fallida"}),
    ("Bloqueos", {"bloqueo", "intento_bloqueado"}),
    ("Contraseñas y recuperación", {"cambio_password", "recuperacion", "recuperacion_fallida",
                                    "codigo_generado"}),
]

_NOMBRE_ROL = {"admin": "Administrador", "vendedor": "Ventas"}


def _badge_evento(fila):
    return _EVENTOS.get(fila["evento"], (fila["evento"], "neutral"))


def _fecha(dt):
    return dt.strftime("%d/%m/%Y %H:%M") if dt else "—"


class SeguridadPage(Page):
    def __init__(self, navigate):
        super().__init__("Seguridad", "Contraseñas, respaldos de la base de datos e historial de "
                                      "accesos al sistema.")
        self.navigate = navigate

        # --- Contrasenas y recuperacion ---
        cuentas = Card("Contraseñas y recuperación")
        fila_cuentas = QHBoxLayout()
        fila_cuentas.setSpacing(16)
        for titulo, texto, boton in (
            ("Cambiar contraseña",
             "Cambia tu contraseña o la de una cuenta de ventas. Se pide tu contraseña actual.",
             button("Cambiar contraseña", "lock", "secondary", on_click=self._cambiar_password)),
            ("Código de recuperación",
             "Genera un código nuevo para recuperar tu contraseña si la olvidas. "
             "El código anterior dejará de funcionar.",
             button("Nuevo código", "key", "secondary", on_click=self._nuevo_codigo)),
        ):
            bloque = QVBoxLayout()
            bloque.setSpacing(6)
            bloque.addWidget(label(titulo, "fieldLabel"))
            bloque.addWidget(label(texto, "caption", wrap=True))
            bloque.addSpacing(4)
            bloque.addWidget(boton, 0, Qt.AlignLeft)
            bloque.addStretch(1)
            fila_cuentas.addLayout(bloque, 1)
        cuentas.body.addLayout(fila_cuentas)
        self.content.addWidget(cuentas)

        # --- Respaldos ---
        respaldos = Card("Respaldos de la base de datos",
                         "Se crea una copia automática cada 2 días al abrir el programa "
                         "o mientras esté abierto.")
        self.boton_respaldo = button("Crear respaldo ahora", "database", "primary",
                                     on_click=self._crear_respaldo)
        respaldos.add_header_widget(self.boton_respaldo)

        datos = QGridLayout()
        datos.setHorizontalSpacing(24)
        datos.setVerticalSpacing(8)
        self.valor_ultimo = label()
        self.valor_proximo = label()
        self.valor_cantidad = label()
        self.valor_carpeta = label(wrap=True)
        for i, (titulo, valor) in enumerate((
            ("Último respaldo", self.valor_ultimo),
            ("Próximo automático", self.valor_proximo),
            ("Respaldos guardados", self.valor_cantidad),
            ("Carpeta", self.valor_carpeta),
        )):
            datos.addWidget(label(titulo, "muted"), i, 0)
            datos.addWidget(valor, i, 1)
        datos.setColumnStretch(1, 1)
        respaldos.body.addLayout(datos)

        acciones = QHBoxLayout()
        acciones.addWidget(label("Para restaurar: cierra el programa y copia el respaldo "
                                 "deseado sobre el archivo tienda_jazmin.db.", "caption", wrap=True), 1)
        acciones.addWidget(button("Abrir carpeta", "folder", "secondary", on_click=self._abrir_carpeta))
        respaldos.body.addLayout(acciones)
        self.content.addWidget(respaldos)

        # --- Historial de accesos ---
        historial = Card("Historial de accesos",
                         "Últimos 1000 eventos. Tras 5 intentos fallidos seguidos, "
                         "el usuario se bloquea 5 minutos.")
        self.filtro = choice_combo(_FILTROS)
        self.filtro.currentIndexChanged.connect(self._aplicar_filtro)
        historial.add_header_widget(self.filtro)
        self.buscador = SearchField("Buscar usuario o detalle")
        self.buscador.textChanged.connect(lambda t: self.tabla.set_filter_text(t))
        historial.add_header_widget(self.buscador)

        self.tabla = DataTable(
            [
                Column("fecha", "Fecha", fmt=fecha_corta, width=150),
                Column("usuario", "Usuario", width=140),
                Column("nombre", "Cuenta", width=190,
                       value=lambda f: (f"{f['nombre']} ({_NOMBRE_ROL.get(f['rol'], f['rol'])})"
                                        if f["nombre"] else "No existe")),
                Column("evento", "Evento", align="center", width=210, badge=_badge_evento),
                Column("detalle", "Detalle", stretch=True),
            ],
            empty_text="Aún no hay accesos registrados.",
            empty_filtered_text="No hay eventos con ese filtro.",
            min_height=360,
        )
        historial.body.addWidget(self.tabla, 1)
        self.resumen = label("", "caption")
        historial.body.addWidget(self.resumen)
        self.content.addWidget(historial, 1)

    def refresh(self):
        estado = controlador_seguridad.obtener_estado_respaldos()
        self._carpeta = estado["carpeta"]
        self.valor_ultimo.setText(_fecha(estado["ultimo"]) if estado["ultimo"] else "Aún no hay respaldos")
        self.valor_proximo.setText(_fecha(estado["proximo"]) if estado["proximo"] else "Al abrir el programa")
        self.valor_cantidad.setText(
            f"{estado['cantidad']} (se conservan los {estado['maximo']} más recientes)")
        self.valor_carpeta.setText(estado["carpeta"])

        filas = controlador_seguridad.obtener_historial_accesos()
        self.tabla.set_rows(filas)
        self.tabla.set_filter_text(self.buscador.text())
        self._aplicar_filtro()

        fallidos = sum(1 for f in filas if f["evento"] in ("fallido", "recuperacion_fallida"))
        bloqueos = sum(1 for f in filas if f["evento"] == "bloqueo")
        self.resumen.setText(f"{plural(len(filas), 'evento', 'eventos')} · "
                             f"{plural(fallidos, 'intento fallido', 'intentos fallidos')} · "
                             f"{plural(bloqueos, 'bloqueo', 'bloqueos')}")

    def _aplicar_filtro(self, *_):
        eventos = self.filtro.currentData()
        self.tabla.set_predicate(None if not eventos else (lambda f: f["evento"] in eventos))

    # Tras cambiar la contrasena o el codigo se recarga para ver el evento en el historial.

    def _cambiar_password(self):
        if self.window().cambiar_password():
            self.refresh()

    def _nuevo_codigo(self):
        if self.window().nuevo_codigo_recuperacion():
            self.refresh()

    def _crear_respaldo(self):
        exito, mensaje = controlador_seguridad.crear_respaldo_manual()
        if exito:
            messages.success(self, "Respaldo creado correctamente.")
            self.refresh()
        else:
            messages.error(self, "No se pudo crear el respaldo", mensaje)

    def _abrir_carpeta(self):
        if not getattr(self, "_carpeta", None):
            self._carpeta = controlador_seguridad.obtener_estado_respaldos()["carpeta"]
        os.makedirs(self._carpeta, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(self._carpeta))
