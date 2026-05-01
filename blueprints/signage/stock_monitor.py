"""
Monitor de stock — detecta productos nuevos con stock bajo y notifica.
"""
import json
import os
from datetime import datetime

from . import odoo_client
from notifications import NotificationManager

# Archivo de estado persistente (relativo a la raíz del proyecto)
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KNOWN_LOW_STOCK_FILE = os.path.join(_BASE_DIR, 'data', 'known_low_stock.json')


class StockMonitor:

    def __init__(self):
        self.nm = NotificationManager()

    # ── Persistencia ──────────────────────────────────────────────────────────

    def _load_known_ids(self) -> set:
        if os.path.exists(KNOWN_LOW_STOCK_FILE):
            try:
                with open(KNOWN_LOW_STOCK_FILE) as f:
                    return set(json.load(f).get('product_ids', []))
            except Exception as e:
                print(f'[StockMonitor] Error leyendo historial: {e}')
        return set()

    def _save_known_ids(self, product_ids: set):
        try:
            os.makedirs(os.path.dirname(KNOWN_LOW_STOCK_FILE), exist_ok=True)
            with open(KNOWN_LOW_STOCK_FILE, 'w') as f:
                json.dump({
                    'product_ids': list(product_ids),
                    'last_check':  datetime.now().isoformat(),
                }, f, indent=2)
        except Exception as e:
            print(f'[StockMonitor] Error guardando historial: {e}')

    # ── Lógica principal ───────────────────────────────────────────────────────

    def _get_new_products(self, current_low: list) -> list:
        current_ids = {p['id'] for p in current_low}
        known_ids   = self._load_known_ids()
        new_ids     = current_ids - known_ids
        self._save_known_ids(current_ids)
        return [p for p in current_low if p['id'] in new_ids]

    def get_low_stock_summary(self) -> tuple:
        """Retorna (productos, error). No envía notificaciones."""
        try:
            models, uid = odoo_client.connect()
            products    = odoo_client.get_low_stock_products(models, uid)
            known_ids   = self._load_known_ids()
            for p in products:
                p['is_new'] = p['id'] not in known_ids
            return products, None
        except Exception as e:
            return None, str(e)

    def check_and_notify(self, force: bool = False) -> tuple:
        """
        Consulta Odoo, detecta stock bajo y notifica.
        force=True → notifica todos; force=False → solo los nuevos.
        Retorna (success, message).
        """
        try:
            models, uid = odoo_client.connect()
            current_low = odoo_client.get_low_stock_products(models, uid)

            if not current_low:
                self._save_known_ids(set())
                return True, 'No hay productos con stock bajo'

            if force:
                to_notify = current_low
                self._save_known_ids({p['id'] for p in current_low})
            else:
                to_notify = self._get_new_products(current_low)

            if not to_notify:
                return True, (
                    f'{len(current_low)} producto(s) siguen con stock bajo — '
                    'sin cambios nuevos, no se enviaron notificaciones'
                )

            text, html, telegram = self.nm.format_low_stock_message(to_notify)
            sent = self.nm.broadcast(
                subject=f'🚨 Stock Bajo: {len(to_notify)} producto(s) nuevo(s)',
                text=text,
                html=html,
                telegram_text=telegram,
                report_type='stock',
            )

            if sent:
                return True, (
                    f'Notificación enviada por {" y ".join(sent)} — '
                    f'{len(to_notify)} producto(s) nuevo(s) con stock bajo'
                )
            return False, (
                f'Se detectaron {len(to_notify)} producto(s) nuevos con stock bajo '
                'pero falló el envío de notificaciones'
            )

        except Exception as e:
            return False, f'Error en verificación de stock: {e}'
