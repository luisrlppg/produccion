-- Migration 001 — schema inicial
-- Aplicada automáticamente al arrancar la app si la tabla no existe.

CREATE TABLE IF NOT EXISTS production_reports (
    id                        INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre                    TEXT    NOT NULL,
    turno                     TEXT    NOT NULL,
    fecha                     TEXT    NOT NULL,
    trabajadores              INTEGER NOT NULL DEFAULT 0,
    maquina1_cantidad         INTEGER NOT NULL DEFAULT 0,
    maquina1_tipo             TEXT    NOT NULL DEFAULT '',
    maquina1_color            TEXT    NOT NULL DEFAULT '',
    maquina2_cantidad         INTEGER NOT NULL DEFAULT 0,
    maquina2_tipo             TEXT    NOT NULL DEFAULT '',
    maquina2_color            TEXT    NOT NULL DEFAULT '',
    maquina3_cantidad         INTEGER NOT NULL DEFAULT 0,
    maquina3_tipo             TEXT    NOT NULL DEFAULT '',
    maquina3_color            TEXT    NOT NULL DEFAULT '',
    ensamble                  TEXT    NOT NULL DEFAULT '',
    ensartado                 TEXT    NOT NULL DEFAULT '',
    pegado                    TEXT    NOT NULL DEFAULT '',
    entregas                  TEXT    NOT NULL DEFAULT '',
    produccion_personal       INTEGER NOT NULL DEFAULT 0,
    produccion_maquinas       INTEGER NOT NULL DEFAULT 0,
    produccion_total          INTEGER NOT NULL DEFAULT 0,
    produccion_por_trabajador REAL    NOT NULL DEFAULT 0,
    notas                     TEXT    NOT NULL DEFAULT '',
    timestamp                 TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS personal_reports (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name           TEXT NOT NULL,
    location            TEXT NOT NULL DEFAULT '',
    failure_description TEXT NOT NULL,
    additional_info     TEXT NOT NULL DEFAULT '',
    photo_path          TEXT NOT NULL DEFAULT '',
    timestamp           TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS company_reports (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    item_name           TEXT NOT NULL,
    location            TEXT NOT NULL DEFAULT '',
    failure_description TEXT NOT NULL,
    additional_info     TEXT NOT NULL DEFAULT '',
    photo_path          TEXT NOT NULL DEFAULT '',
    timestamp           TEXT NOT NULL
);

-- Índices útiles para consultas frecuentes
CREATE INDEX IF NOT EXISTS idx_production_fecha     ON production_reports(fecha);
CREATE INDEX IF NOT EXISTS idx_production_turno     ON production_reports(turno);
CREATE INDEX IF NOT EXISTS idx_production_timestamp ON production_reports(timestamp);
