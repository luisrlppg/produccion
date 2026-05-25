-- Migration 005 — columna JSON para múltiples producciones por máquina
ALTER TABLE production_reports ADD COLUMN maquinas TEXT NOT NULL DEFAULT '';
