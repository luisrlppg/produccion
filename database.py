"""
database.py — capa de acceso a datos SQLite para PPG Unified.
"""

import csv
import io
import json
import os
import sqlite3
from contextlib import contextmanager

DB_PATH        = os.getenv('DB_PATH', 'data/ppg.db')
MIGRATIONS_DIR = 'data/migrations'


# ── Conexión ───────────────────────────────────────────────────────────────────

@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Migraciones ────────────────────────────────────────────────────────────────

def _ensure_migrations_table(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS _migrations (
            name       TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def _applied_migrations(conn) -> set:
    return {row[0] for row in conn.execute('SELECT name FROM _migrations')}


def run_migrations():
    os.makedirs(MIGRATIONS_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    try:
        _ensure_migrations_table(conn)
        applied = _applied_migrations(conn)
        files = sorted(
            f for f in os.listdir(MIGRATIONS_DIR)
            if f.endswith('.sql') and f not in applied
        )
        for fname in files:
            path = os.path.join(MIGRATIONS_DIR, fname)
            with open(path, encoding='utf-8') as f:
                sql = f.read()
            conn.executescript(sql)
            conn.execute('INSERT INTO _migrations (name) VALUES (?)', (fname,))
            conn.commit()
            print(f'[DB] Migración aplicada: {fname}')
        if not files:
            print('[DB] Sin migraciones pendientes.')
    finally:
        conn.close()


def _migrate_old_machine_data():
    """Migra datos de columnas viejas (maquina1_cantidad, etc.) a la columna maquinas JSON."""
    with get_db() as db:
        rows = db.execute(
            "SELECT id, maquina1_cantidad, maquina1_tipo, maquina1_color, "
            "maquina2_cantidad, maquina2_tipo, maquina2_color, "
            "maquina3_cantidad, maquina3_tipo, maquina3_color "
            "FROM production_reports WHERE maquinas IS NULL OR maquinas = ''"
        ).fetchall()
        for r in rows:
            machines = []
            for i in range(1, 4):
                qty = r[f'maquina{i}_cantidad']
                if qty and int(qty) > 0:
                    machines.append({
                        'maquina': i,
                        'cantidad': int(qty),
                        'tipo': r[f'maquina{i}_tipo'] or '',
                        'color': r[f'maquina{i}_color'] or '',
                    })
            db.execute(
                "UPDATE production_reports SET maquinas = ? WHERE id = ?",
                (json.dumps(machines, ensure_ascii=False), r['id'])
            )
    if rows:
        print(f'[DB] Migradas {len(rows)} filas a columna maquinas')


def parse_maquinas(report: dict) -> list[dict]:
    """Lee la columna `maquinas` (JSON) y retorna lista de dicts.
    Si está vacía, retrocede a las columnas viejas (maquina1_cantidad, etc.)"""
    raw = report.get('maquinas', '') or ''
    if raw:
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pass
    machines = []
    for i in range(1, 4):
        qty = report.get(f'maquina{i}_cantidad') or 0
        if qty and int(qty) > 0:
            machines.append({
                'maquina': i,
                'cantidad': int(qty),
                'tipo': report.get(f'maquina{i}_tipo', '') or '',
                'color': report.get(f'maquina{i}_color', '') or '',
            })
    return machines


def format_maquinas_text(machines: list[dict]) -> str:
    """Formatea lista de máquinas a texto plano para CSV."""
    return ' | '.join(
        f'M{m["maquina"]}: {m["cantidad"]} {m["tipo"]} {m["color"]}'
        for m in machines
    )


def init_db(app):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    run_migrations()
    _migrate_old_machine_data()
    print(f'[DB] Lista en {DB_PATH}')


# ── Config options (brush types & colors) ──────────────────────────────────────

def get_config_options(option_type: str) -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            'SELECT id, option_type, option_key, option_label, sort_order '
            'FROM config_options WHERE option_type = ? ORDER BY sort_order, id',
            (option_type,)
        ).fetchall()
        return [dict(r) for r in rows]


def add_config_option(option_type: str, option_key: str, option_label: str, sort_order: int = 0) -> int:
    with get_db() as db:
        cur = db.execute(
            'INSERT INTO config_options (option_type, option_key, option_label, sort_order) '
            'VALUES (?, ?, ?, ?)',
            (option_type, option_key, option_label, sort_order)
        )
        return cur.lastrowid


def get_config_option_label(option_key: str) -> str | None:
    with get_db() as db:
        row = db.execute(
            'SELECT option_label FROM config_options WHERE option_key = ? LIMIT 1',
            (option_key,)
        ).fetchone()
        return row[0] if row else None


# ── Production reports ─────────────────────────────────────────────────────────

def insert_production_report(
    nombre, turno, fecha, trabajadores,
    maquina1_cantidad, maquina1_tipo, maquina1_color,
    maquina2_cantidad, maquina2_tipo, maquina2_color,
    maquina3_cantidad, maquina3_tipo, maquina3_color,
    section_data: dict,
    section_totals: dict,
    entregas,
    produccion_personal, produccion_maquinas, produccion_total,
    produccion_por_persona_hora, notas, timestamp,
    maquinas='',
) -> int:
    """Inserta un reporte de producción y retorna el ID generado."""
    from blueprints.reports.production_sections import PRODUCTION_SECTIONS, SECTION_KEYS
    section_cols        = ', '.join(SECTION_KEYS)
    section_placeholders = ', '.join('?' for _ in SECTION_KEYS)
    section_vals        = [section_data.get(k, '') for k in SECTION_KEYS]

    total_cols         = ', '.join(s['total_col'] for s in PRODUCTION_SECTIONS)
    total_placeholders = ', '.join('?' for _ in PRODUCTION_SECTIONS)
    total_vals         = [section_totals.get(s['key'], 0) for s in PRODUCTION_SECTIONS]

    with get_db() as db:
        cur = db.execute(f"""
            INSERT INTO production_reports (
                nombre, turno, fecha, trabajadores,
                maquina1_cantidad, maquina1_tipo, maquina1_color,
                maquina2_cantidad, maquina2_tipo, maquina2_color,
                maquina3_cantidad, maquina3_tipo, maquina3_color,
                {section_cols}, {total_cols}, entregas,
                produccion_personal, produccion_maquinas, produccion_total,
                produccion_por_persona_hora, notas, timestamp,
                maquinas
            ) VALUES (
                ?,?,?,?,
                ?,?,?,
                ?,?,?,
                ?,?,?,
                {section_placeholders}, {total_placeholders}, ?,
                ?,?,?,
                ?,?,?,
                ?
            )
        """, (
            nombre, turno, fecha, trabajadores,
            maquina1_cantidad, maquina1_tipo, maquina1_color,
            maquina2_cantidad, maquina2_tipo, maquina2_color,
            maquina3_cantidad, maquina3_tipo, maquina3_color,
            *section_vals, *total_vals, entregas,
            produccion_personal, produccion_maquinas, produccion_total,
            produccion_por_persona_hora, notas, timestamp,
            maquinas,
        ))
        return cur.lastrowid


def get_production_report_by_id(report_id: int) -> dict | None:
    with get_db() as db:
        row = db.execute(
            'SELECT * FROM production_reports WHERE id = ?', (report_id,)
        ).fetchone()
        return dict(row) if row else None


def get_production_reports(fecha: str | None = None) -> list[dict]:
    with get_db() as db:
        if fecha:
            rows = db.execute(
                'SELECT * FROM production_reports WHERE fecha = ? ORDER BY id',
                (fecha,)
            ).fetchall()
        else:
            rows = db.execute(
                'SELECT * FROM production_reports ORDER BY timestamp DESC'
            ).fetchall()
        return [dict(r) for r in rows]


def get_production_dates() -> list[str]:
    with get_db() as db:
        rows = db.execute(
            'SELECT DISTINCT fecha FROM production_reports ORDER BY fecha DESC'
        ).fetchall()
        return [r[0] for r in rows]


def get_all_production_reports() -> list[dict]:
    with get_db() as db:
        rows = db.execute(
            'SELECT * FROM production_reports ORDER BY timestamp DESC'
        ).fetchall()
        return [dict(r) for r in rows]


def update_production_report(report_id: int, **fields) -> bool:
    if not fields:
        return False
    cols = ', '.join(f'{k} = ?' for k in fields)
    vals = list(fields.values()) + [report_id]
    with get_db() as db:
        cur = db.execute(
            f'UPDATE production_reports SET {cols} WHERE id = ?', vals
        )
        return cur.rowcount > 0


def delete_production_report(report_id: int) -> bool:
    with get_db() as db:
        cur = db.execute(
            'DELETE FROM production_reports WHERE id = ?', (report_id,)
        )
        return cur.rowcount > 0


# ── Personal / Company reports ─────────────────────────────────────────────────

def insert_simple_report(
    table: str,
    item_name: str, location: str, failure_description: str,
    additional_info: str, photo_path: str, timestamp: str,
) -> int:
    assert table in ('personal_reports', 'company_reports')
    with get_db() as db:
        cur = db.execute(f"""
            INSERT INTO {table}
                (item_name, location, failure_description, additional_info, photo_path, timestamp)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (item_name, location, failure_description, additional_info, photo_path, timestamp))
        return cur.lastrowid


def get_simple_reports(table: str) -> list[dict]:
    assert table in ('personal_reports', 'company_reports')
    with get_db() as db:
        rows = db.execute(
            f'SELECT * FROM {table} ORDER BY id DESC'
        ).fetchall()
        return [dict(r) for r in rows]


# ── Exportación CSV ────────────────────────────────────────────────────────────

PRODUCTION_CSV_HEADER = [
    'ID Reporte', 'Nombre', 'Turno', 'Fecha', 'Trabajadores',
    'Maquina 1 Cantidad', 'Maquina 1 Tipo de Cepillo', 'Maquina 1 Color',
    'Maquina 2 Cantidad', 'Maquina 2 Tipo de Cepillo', 'Maquina 2 Color',
    'Maquina 3 Cantidad', 'Maquina 3 Tipo de Cepillo', 'Maquina 3 Color',
    'Ensamble', 'Ensartado', 'Pegado', 'Perforado', 'Entregas',
    'Produccion Personal', 'Produccion Maquinas', 'Produccion Total',
    'Produccion por Persona por Hora', 'Notas Adicionales', 'Fecha y Hora de Envio',
]

SIMPLE_CSV_HEADER = [
    'Report_ID', 'Item_Name', 'Location',
    'Failure_Description', 'Additional_Info', 'Photo_Path', 'Timestamp',
]


def export_production_csv() -> str:
    from blueprints.reports.production_sections import PRODUCTION_SECTIONS
    rows = get_all_production_reports()
    buf  = io.StringIO()
    # BOM UTF-8 para que Excel reconozca el encoding correctamente
    buf.write('\ufeff')
    w    = csv.writer(buf)
    # Header dinámico
    section_labels = [s['csv_label'] for s in PRODUCTION_SECTIONS]
    header = [
        'ID Reporte', 'Nombre', 'Turno', 'Fecha', 'Trabajadores',
        'Maquina 1 Cantidad', 'Maquina 1 Tipo de Cepillo', 'Maquina 1 Color',
        'Maquina 2 Cantidad', 'Maquina 2 Tipo de Cepillo', 'Maquina 2 Color',
        'Maquina 3 Cantidad', 'Maquina 3 Tipo de Cepillo', 'Maquina 3 Color',
        *section_labels, 'Entregas',
        'Produccion Personal', 'Produccion Maquinas', 'Produccion Total',
        'Produccion por Persona por Hora', 'Notas Adicionales', 'Fecha y Hora de Envio',
        'Detalle Maquinas',
    ]
    w.writerow(header)
    for r in rows:
        section_vals = [r.get(s['key'], '') for s in PRODUCTION_SECTIONS]
        maquinas_text = format_maquinas_text(parse_maquinas(r))
        w.writerow([
            r['id'], r['nombre'], r['turno'], r['fecha'], r['trabajadores'],
            r['maquina1_cantidad'], r['maquina1_tipo'], r['maquina1_color'],
            r['maquina2_cantidad'], r['maquina2_tipo'], r['maquina2_color'],
            r['maquina3_cantidad'], r['maquina3_tipo'], r['maquina3_color'],
            *section_vals, r['entregas'],
            r['produccion_personal'], r['produccion_maquinas'], r['produccion_total'],
            r['produccion_por_persona_hora'], r['notas'], r['timestamp'],
            maquinas_text,
        ])
    return buf.getvalue()


def export_simple_csv(table: str) -> str:
    rows = get_simple_reports(table)
    buf  = io.StringIO()
    # BOM UTF-8 para que Excel reconozca el encoding correctamente
    buf.write('\ufeff')
    w    = csv.writer(buf)
    w.writerow(SIMPLE_CSV_HEADER)
    for r in rows:
        w.writerow([
            r['id'], r['item_name'], r['location'],
            r['failure_description'], r['additional_info'],
            r['photo_path'], r['timestamp'],
        ])
    return buf.getvalue()
