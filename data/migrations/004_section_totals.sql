-- Migration 004 — totales numéricos por sección de producción manual
ALTER TABLE production_reports ADD COLUMN total_ensamble  INTEGER NOT NULL DEFAULT 0;
ALTER TABLE production_reports ADD COLUMN total_ensartado INTEGER NOT NULL DEFAULT 0;
ALTER TABLE production_reports ADD COLUMN total_pegado    INTEGER NOT NULL DEFAULT 0;
ALTER TABLE production_reports ADD COLUMN total_perforado INTEGER NOT NULL DEFAULT 0;
