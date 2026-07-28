-- Migration 006 — config_options table for dynamic brush types and colors

CREATE TABLE IF NOT EXISTS config_options (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    option_type TEXT    NOT NULL,
    option_key  TEXT    NOT NULL,
    option_label TEXT   NOT NULL,
    sort_order   INTEGER DEFAULT 0,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_config_type_key ON config_options(option_type, option_key);

-- Seed existing brush types
INSERT INTO config_options (option_type, option_key, option_label, sort_order) VALUES
    ('brush_type', 'straight',    'Recto',       1),
    ('brush_type', 'spiral',      'Espiral',     2),
    ('brush_type', 'bullet',      'Bala',        3),
    ('brush_type', 'mini_bullet', 'Balita',      4),
    ('brush_type', 'pine',        'Pino',        5),
    ('brush_type', 'peanut',      'Cacahuate',   6),
    ('brush_type', 'balloon',     'Globo',       7);

-- Seed existing colors
INSERT INTO config_options (option_type, option_key, option_label, sort_order) VALUES
    ('color', 'black',       'Negro',       1),
    ('color', 'brown',       'Cafe',        2),
    ('color', 'blue',        'Azul',        3),
    ('color', 'green',       'Verde',       4),
    ('color', 'turquoise',   'Turquesa',    5),
    ('color', 'pink',        'Rosa',        6),
    ('color', 'purple',      'Morado',      7),
    ('color', 'transparent', 'Transparente', 8);
