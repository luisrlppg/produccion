"""
Cliente Odoo — único punto de contacto con la API XML-RPC.
"""
import xmlrpc.client
import os
from dotenv import load_dotenv

load_dotenv()

ODOO_URL      = os.getenv('ODOO_URL',      'http://192.168.1.160:8070/')
ODOO_DB       = os.getenv('ODOO_DB',       'ppg')
ODOO_USERNAME = os.getenv('ODOO_USERNAME', 'admin')
ODOO_PASSWORD = os.getenv('ODOO_PASSWORD', 'odooppg')


def connect():
    common = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/common')
    models = xmlrpc.client.ServerProxy(f'{ODOO_URL}/xmlrpc/2/object')
    uid = common.authenticate(ODOO_DB, ODOO_USERNAME, ODOO_PASSWORD, {})
    if not uid:
        raise ConnectionError('Autenticación con Odoo fallida — verifica credenciales')
    return models, uid


def _execute(models, uid, model, method, domain, fields):
    return models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD, model, method,
        [domain], {'fields': fields}
    )


def _read(models, uid, model, ids, fields):
    return models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD, model, 'read',
        [ids], {'fields': fields}
    )


def get_active_manufacturing_orders(models, uid):
    return _execute(
        models, uid,
        model='mrp.production',
        method='search_read',
        domain=[
            ('state', 'in', ['confirmed', 'progress', 'to_close']),
            ('name', 'not like', 'SBC%'),
        ],
        fields=['name', 'product_id', 'product_qty', 'state', 'date_start'],
    )


def get_product_categories(models, uid, product_ids):
    return _read(models, uid, 'product.product', product_ids, ['categ_id'])


def get_reordering_rules(models, uid):
    return _execute(
        models, uid,
        model='stock.warehouse.orderpoint',
        method='search_read',
        domain=[],
        fields=['product_id', 'product_min_qty', 'product_max_qty'],
    )


def get_products_stock(models, uid, product_ids):
    return _read(
        models, uid, 'product.product', product_ids,
        ['name', 'qty_available', 'virtual_available'],
    )


def get_manufacturing_totals_by_category(models, uid, orders):
    categories = {
        'ensamble':  {'total': {}, 'names': {}},
        'cepillo':   {'total': {}, 'names': {}},
        'inyeccion': {'total': {}, 'names': {}},
    }
    if not orders:
        return categories

    product_ids = [o['product_id'][0] for o in orders]
    raw_categories = get_product_categories(models, uid, product_ids)

    product_to_category = {}
    for p in raw_categories:
        categ_name = p['categ_id'][1].lower() if p.get('categ_id') else ''
        if 'ensamble' in categ_name or 'pincel' in categ_name:
            product_to_category[p['id']] = 'ensamble'
        elif 'cepillo' in categ_name:
            product_to_category[p['id']] = 'cepillo'
        else:
            product_to_category[p['id']] = 'inyeccion'

    for order in orders:
        pid  = order['product_id'][0]
        name = order['product_id'][1]
        qty  = order['product_qty']
        cat  = product_to_category.get(pid, 'inyeccion')
        if pid in categories[cat]['total']:
            categories[cat]['total'][pid] += qty
        else:
            categories[cat]['total'][pid]  = qty
            categories[cat]['names'][pid]  = name

    return categories


def get_low_stock_products(models, uid):
    rules = get_reordering_rules(models, uid)
    if not rules:
        return []

    reorder_map = {}
    for rule in rules:
        pid = rule['product_id'][0]
        reorder_map.setdefault(pid, []).append(rule['product_min_qty'])

    products = get_products_stock(models, uid, list(reorder_map.keys()))

    low = []
    for p in products:
        pid     = p['id']
        min_qty = min(reorder_map[pid])
        current = p['qty_available']
        if current < min_qty:
            low.append({
                'id':                 pid,
                'name':               p['name'],
                'qty_available':      current,
                'virtual_available':  p['virtual_available'],
                'reordering_min_qty': min_qty,
                'difference':         current - min_qty,
            })
    return low
