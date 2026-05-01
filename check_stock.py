#!/usr/bin/env python3
"""
Verificación manual de stock bajo.
Ejecutar directamente o desde cron:

  python check_stock.py           # verifica y notifica solo productos nuevos
  python check_stock.py --force   # notifica todos los productos con stock bajo

Ejemplo cron (3 veces al día):
  0 8,14,18 * * * cd /app && python check_stock.py >> /var/log/stock_check.log 2>&1
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Asegurar que el directorio raíz esté en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from blueprints.signage.stock_monitor import StockMonitor


def main():
    force   = '--force' in sys.argv
    monitor = StockMonitor()

    print(f"\n{'='*50}")
    print(f"Verificación de stock — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Modo: {'forzado (todos)' if force else 'solo nuevos'}")
    print(f"{'='*50}")

    success, message = monitor.check_and_notify(force=force)
    print(f"{'✅' if success else '❌'} {message}")
    print(f"{'='*50}\n")

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
