"""
scripts/recalculate_section_totals.py

Recalcula total_ensamble, total_ensartado, total_pegado, total_perforado
para todos los reportes existentes que tengan esas columnas en cero.

Ejecutar una sola vez después de la migración 004:
    python scripts/recalculate_section_totals.py
"""
import os
import sys
import sqlite3

# Asegurar que el path raíz del proyecto esté en sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from blueprints.reports.production_sections import PRODUCTION_SECTIONS

DB_PATH = os.getenv('DB_PATH', 'data/ppg.db')


def parse_total(text: str) -> int:
    """Suma las cantidades de un string tipo 'Producto A: 10, Producto B: 5'."""
    total = 0
    if not text:
        return 0
    for item in text.split(', '):
        if ': ' in item:
            _, qty = item.split(': ', 1)
            try:
                total += int(qty.strip())
            except ValueError:
                pass
    return total


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute('SELECT id, ' +
                        ', '.join(s['key'] for s in PRODUCTION_SECTIONS) +
                        ' FROM production_reports').fetchall()

    updated = 0
    for row in rows:
        updates = {}
        for s in PRODUCTION_SECTIONS:
            total = parse_total(row[s['key']] or '')
            updates[s['total_col']] = total

        set_clause = ', '.join(f"{col} = ?" for col in updates)
        conn.execute(
            f"UPDATE production_reports SET {set_clause} WHERE id = ?",
            (*updates.values(), row['id'])
        )
        updated += 1

    conn.commit()
    conn.close()
    print(f'[OK] {updated} reportes actualizados.')


if __name__ == '__main__':
    main()
