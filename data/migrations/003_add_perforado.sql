-- Migration 003 — agregar columna perforado a production_reports
ALTER TABLE production_reports ADD COLUMN perforado TEXT NOT NULL DEFAULT '';
