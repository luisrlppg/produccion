"""
production_sections.py — fuente única de verdad para las secciones de producción.

Para agregar una sección nueva:
  1. Agregar una entrada a PRODUCTION_SECTIONS
  2. Crear una migración SQL con:
       ALTER TABLE production_reports ADD COLUMN <key>       TEXT    NOT NULL DEFAULT '';
       ALTER TABLE production_reports ADD COLUMN total_<key> INTEGER NOT NULL DEFAULT 0;

Para quitar una sección:
  1. Eliminarla de PRODUCTION_SECTIONS
  (las columnas en la DB se mantienen pero ya no se usan)

Campos de cada sección:
  - key:        nombre de la columna de texto en la DB y del campo JSON oculto en el form
  - total_col:  nombre de la columna numérica de total en la DB
  - label:      título visible en el formulario y en la vista
  - css_prefix: prefijo CSS/JS para las filas dinámicas del formulario
  - json_key:   clave en production_details.json
  - csv_label:  nombre de la columna de texto en el CSV exportado
"""

PRODUCTION_SECTIONS = [
    {
        'key':        'ensamble',
        'total_col':  'total_ensamble',
        'label':      'Ensamble',
        'css_prefix': 'assembly',
        'json_key':   'ensamble',
        'csv_label':  'Ensamble',
    },
    {
        'key':        'ensartado',
        'total_col':  'total_ensartado',
        'label':      'Ensartado',
        'css_prefix': 'stringing',
        'json_key':   'ensartado',
        'csv_label':  'Ensartado',
    },
    {
        'key':        'pegado',
        'total_col':  'total_pegado',
        'label':      'Pegado',
        'css_prefix': 'gluing',
        'json_key':   'pegado',
        'csv_label':  'Pegado',
    },
    {
        'key':        'perforado',
        'total_col':  'total_perforado',
        'label':      'Perforado',
        'css_prefix': 'drilling',
        'json_key':   'perforado',
        'csv_label':  'Perforado',
    },
]

# Acceso rápido por key
SECTIONS_BY_KEY = {s['key']: s for s in PRODUCTION_SECTIONS}

# Lista de keys para iterar
SECTION_KEYS = [s['key'] for s in PRODUCTION_SECTIONS]
