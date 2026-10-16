"""
Modulo de reportes.

  periodos.py  calculo de rangos de fechas (diario, semanal, mensual, anual)
  formato.py   formatos de numeros y textos propios de los reportes
  resumen.py   redaccion automatica del resumen del periodo
  pdf.py       generacion del documento PDF con ReportLab
  pdf_existencias.py  PDF de los articulos en stock (reutiliza el formato de pdf.py)

Las consultas SQL estan en models/reportes.py y la orquestacion en
controllers/controlador_reportes.py, siguiendo la arquitectura MVC del proyecto.
"""
