"""
database.py — capa de acceso a datos SQLite para PPG Unified.

Uso:
    from database import get_db, init_db

    # En app.py al arrancar:
    init_db(app)

    # En cualquier ruta:
    with get_db() as db:
        db.execute("INSERT INTO ...")

Migraciones:
    Agregar archivos SQL numerados en data/migrations/
    (002_add_column.sql, 003_...) — se aplican automáticamente
    en orden si aún no han sido registradas en la tabla _migrations.
"""

import csv
import io
import os
import sqlite3
from contextlib import contextmanager

DB_PATH         = os.getenv('DB_PATH', 'data/ppg.db')
MIGRATIONS_DIR  = 'data/migrations'


# ── Conexión ───────────────────────────────────────────────────────────────────

@contextmanager
def get_db():
    """Context manager que entrega una conexión con row_factory y cierra al salir."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')   # mejor concurrencia con gunicorn
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
            name      TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()


def _applied_migrations(conn) -> set:
    return {row[0] for row in conn.execute('SELECT name FROM _migrations')}


def run_migrations():
    """Aplica todos los archivos .sql de MIGRATIONS_DIR que aún no se han ejecutado."""
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
            conn.execute(
                'INSERT INTO _migrations (name) VALUES (?)', (fname,)
            )
            conn.commit()
            print(f'[DB] Migración aplicada: {fname}')

        if not files:
            print('[DB] Sin migraciones pendientes.')
    finally:
        conn.close()


def init_db(app):
    """Llamar desde create_app() — inicializa la DB y corre migraciones."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    run_migrations()
    print(f'[DB] Lista en {DB_PATH}')


# ── Production reports ─────────────────────────────────────────────────────────

def insert_production_report(
    nombre, turno, fecha, trabajadores,
    maquina1_cantidad, maquina1_tipo, maquina1_color,
    maquina2_cantidad, maquina2_tipo, maquina2_color,
    maquina3_cantidad, maquina3_tipo, maquina3_color,
    ensamble, ensartado, pegado, entregas,
    produccion_personal, produccion_maquinas, produccion_total,
    produccion_por_trabajador, notas, timestamp,
) -> int:
    """Inserta un reporte de producción y retorna el ID generado."""
    with get_db() as db:
        cur = db.execute("""
            INSERT INTO production_reports (
                nombre, turno, fecha, trabajadores,
                maquina1_cantidad, maquina1_tipo, maquina1_color,
                maquina2_cantidad, maquina2_tipo, maquina2_color,
                maquina3_cantidad, maquina3_tipo, maquina3_color,
                ensamble, ensartado, pegado, entregas,
                produccion_personal, produccion_maquinas, produccion_total,
                produccion_por_trabajador, notas, timestamp
            ) VALUES (
                ?,?,?,?,
                ?,?,?,
                ?,?,?,
                ?,?,?,
                ?,?,?,?,
                ?,?,?,
                ?,?,?
            )
        """, (
            nombre, turno, fecha, trabajadores,
            maquina1_cantidad, maquina1_tipo, maquina1_color,
            maquina2_cantidad, maquina2_tipo, maquina2_color,
            maquina3_cantidad, maquina3_tipo, maquina3_color,
            ensamble, ensartado, pegado, entregas,
            produccion_personal, produccion_maquinas, produccion_total,
            produccion_por_trabajador, notas, timestamp,
        ))
        return cur.lastrowid


def get_production_reports(fecha: str | None = None) -> list[dict]:
    """Retorna todos los reportes o los de una fecha específica, como lista de dicts."""
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
    """Retorna lista de fechas únicas con reportes, ordenadas descendente."""
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


# ── Personal / Company reports ─────────────────────────────────────────────────

def insert_simple_report(
    table: str,
    item_name: str, location: str, failure_description: str,
    additional_info: str, photo_path: str, timestamp: str,
) -> int:
    """Inserta un reporte personal o de empresa y retorna el ID."""
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
    'Ensamble', 'Ensartado', 'Pegado', 'Entregas',
    'Produccion Personal', 'Produccion Maquinas', 'Produccion Total',
    'Produccion por Trabajador', 'Notas Adicionales', 'Fecha y Hora de Envio',
]

SIMPLE_CSV_HEADER = [
    'Report_ID', 'Item_Name', 'Location',
    'Failure_Description', 'Additional_Info', 'Photo_Path', 'Timestamp',
]


def export_production_csv() -> str:
    """Genera el contenido CSV de producción como string UTF-8."""
    rows = get_all_production_reports()
    buf  = io.StringIO()
    w    = csv.writer(buf)
    w.writerow(PRODUCTION_CSV_HEADER)
    for r in rows:
        w.writerow([
            r['id'], r['nombre'], r['turno'], r['fecha'], r['trabajadores'],
            r['maquina1_cantidad'], r['maquina1_tipo'], r['maquina1_color'],
            r['maquina2_cantidad'], r['maquina2_tipo'], r['maquina2_color'],
            r['maquina3_cantidad'], r['maquina3_tipo'], r['maquina3_color'],
            r['ensamble'], r['ensartado'], r['pegado'], r['entregas'],
            r['produccion_personal'], r['produccion_maquinas'], r['produccion_total'],
            r['produccion_por_trabajador'], r['notas'], r['timestamp'],
        ])
    return buf.getvalue()


def export_simple_csv(table: str) -> str:
    """Genera el contenido CSV de personal o empresa como string UTF-8."""
    rows = get_simple_reports(table)
    buf  = io.StringIO()
    w    = csv.writer(buf)
    w.writerow(SIMPLE_CSV_HEADER)
    for r in rows:
        w.writerow([
            r['id'], r['item_name'], r['location'],
            r['failure_description'], r['additional_info'],
            r['photo_path'], r['timestamp'],
        ])
    return buf.getvalue()
