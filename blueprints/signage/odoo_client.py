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
        ['display_name', 'qty_available',
         'product_tmpl_id', 'product_tag_ids'],
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


def get_sales_orders(models, uid):
    """
    Trae órdenes de venta confirmadas con sus líneas, cliente,
    estado de entrega y stock disponible de cada producto.
    Retorna una lista de órdenes con sus líneas enriquecidas.
    """
    # 1. Órdenes de venta confirmadas o en progreso
    orders = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'sale.order', 'search_read',
        [[('state', 'in', ['sale', 'done'])]],
        {'fields': ['name', 'partner_id', 'date_order', 'state',
                    'delivery_status', 'order_line', 'amount_total'],
         'order': 'date_order desc',
         'limit': 100},
    )
    if not orders:
        return []

    # 2. Líneas de venta — una sola llamada batch
    all_line_ids = [lid for o in orders for lid in o['order_line']]
    lines_raw = models.execute_kw(
        ODOO_DB, uid, ODOO_PASSWORD,
        'sale.order.line', 'read',
        [all_line_ids],
        {'fields': ['order_id', 'product_id', 'product_uom_qty',
                    'qty_delivered', 'qty_invoiced', 'price_unit', 'price_subtotal']},
    )

    # 3. Stock disponible — una sola llamada batch con todos los product_ids únicos
    product_ids = list({l['product_id'][0] for l in lines_raw if l.get('product_id')})
    stock_raw = _read(models, uid, 'product.product', product_ids, ['qty_available'])
    stock_map = {p['id']: p['qty_available'] for p in stock_raw}

    # 4. Agrupar líneas por orden
    lines_by_order = {}
    for line in lines_raw:
        oid = line['order_id'][0]
        lines_by_order.setdefault(oid, []).append(line)

    # 5. Construir resultado final
    result = []
    for o in orders:
        lines = []
        for l in lines_by_order.get(o['id'], []):
            pid = l['product_id'][0] if l.get('product_id') else None
            lines.append({
                'product_name':   l['product_id'][1] if l.get('product_id') else '—',
                'ordered_qty':    l['product_uom_qty'],
                'delivered_qty':  l['qty_delivered'],
                'qty_available':  stock_map.get(pid, 0) if pid else 0,
                'price_unit':     l['price_unit'],
                'price_subtotal': l['price_subtotal'],
            })

        # Estado de entrega normalizado
        delivery_status = o.get('delivery_status', '')
        if not delivery_status:
            # Calcular desde líneas si Odoo no lo devuelve
            total_ord = sum(l['ordered_qty']   for l in lines)
            total_del = sum(l['delivered_qty'] for l in lines)
            if total_del == 0:
                delivery_status = 'pending'
            elif total_del >= total_ord:
                delivery_status = 'full'
            else:
                delivery_status = 'partial'

        result.append({
            'id':              o['id'],
            'name':            o['name'],
            'partner':         o['partner_id'][1] if o.get('partner_id') else '—',
            'date':            o['date_order'][:10] if o.get('date_order') else '—',
            'state':           o['state'],
            'delivery_status': delivery_status,
            'amount_total':    o.get('amount_total', 0),
            'lines':           lines,
        })
    return result


def get_low_stock_products(models, uid):
    rules = get_reordering_rules(models, uid)
    if not rules:
        return []

    reorder_map = {}
    for rule in rules:
        pid = rule['product_id'][0]
        reorder_map.setdefault(pid, {'min': [], 'max': []})
        reorder_map[pid]['min'].append(rule['product_min_qty'])
        reorder_map[pid]['max'].append(rule['product_max_qty'])

    products = get_products_stock(models, uid, list(reorder_map.keys()))

    # display_name ya incluye la variante (ej. "Cepillo Recto (Rojo)")
    # product_tmpl_id[1] es el nombre base del template sin variante
    all_tag_ids = []
    for p in products:
        all_tag_ids.extend(p.get('product_tag_ids') or [])

    # Batch: leer nombres de tags en una sola llamada
    long_lead_ids = set()
    if all_tag_ids:
        tag_records = models.execute_kw(
            ODOO_DB, uid, ODOO_PASSWORD,
            'product.tag', 'read',
            [list(set(all_tag_ids))],
            {'fields': ['name']},
        )
        long_lead_ids = {
            r['id'] for r in tag_records
            if 'long lead' in r['name'].lower()
        }

    low = []
    for p in products:
        pid     = p['id']
        min_qty = min(reorder_map[pid]['min'])
        max_qty = max(reorder_map[pid]['max'])
        current = p['qty_available']
        if current < min_qty:
            tmpl      = p.get('product_tmpl_id')
            base_name = tmpl[1] if isinstance(tmpl, (list, tuple)) and len(tmpl) > 1 else p['display_name']
            full_name = p['display_name']
            # Extraer variante: todo lo que está entre paréntesis en display_name
            variant = ''
            if '(' in full_name and full_name.endswith(')'):
                raw_variant = full_name[full_name.index('(')+1:-1]
                variant = ' | '.join(v.strip() for v in raw_variant.split(','))
            low.append({
                'id':                 pid,
                'name':               base_name,
                'variant':            variant,
                'qty_available':      current,
                'reordering_min_qty': min_qty,
                'reordering_max_qty': max_qty,
                'difference':         current - min_qty,
                'is_long_lead':       bool(set(p.get('product_tag_ids') or []) & long_lead_ids),
            })
    return low
