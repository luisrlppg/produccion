-- Migration 002 — renombrar produccion_por_trabajador → produccion_por_persona_hora
-- SQLite no soporta RENAME COLUMN antes de 3.25, usamos recreación de tabla.

ALTER TABLE production_reports
    RENAME COLUMN produccion_por_trabajador TO produccion_por_persona_hora;
