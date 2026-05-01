"""
Blueprint de Signage — producción en pantalla + monitor de stock.
Prefijo: /signage

Flujo de datos:
  1. Panel carga datos de Odoo  → GET  /signage/data         (requiere auth)
     └─ devuelve datos al cliente, NO guarda nada en servidor
  2. Panel guarda selección     → POST /signage/update-display (requiere auth)
     └─ recibe los items seleccionados (id, name, qty, cat) desde el form
     └─ guarda SOLO esos items en _display_cache (memoria del servidor)
     └─ empuja evento SSE a todos los displays conectados
  3. Display escucha SSE        → GET  /signage/events        (público)
     └─ recibe los items seleccionados al instante
     └─ no guarda nada, no hace fetch, no usa storage
"""
import json
import os
import queue
import threading
from datetime import datetime

from flask import (Blueprint, Response, jsonify, redirect, render_template,
                   request, stream_with_context, url_for)

from auth import signage_login_required as login_required
from notifications import NotificationManager
from . import odoo_client
from .stock_monitor import StockMonitor

signage_bp = Blueprint(
    'signage', __name__,
    url_prefix='/signage',
    template_folder='../../templates/signage',
)

# ── Única memoria del servidor ─────────────────────────────────────────────────
# Solo contiene los items que el usuario seleccionó y guardó desde el panel.
# Se resetea al reiniciar el proceso. Nada más se almacena aquí.
_display_cache: dict | None = None
_cache_lock = threading.Lock()

# ── SSE: suscriptores de display ───────────────────────────────────────────────
_sse_subscribers: list[queue.Queue] = []
_sse_lock = threading.Lock()

stock_monitor = StockMonitor()


def _push_to_displays(payload: dict):
    """Envía payload a todos los clientes SSE conectados."""
    msg = f"data: {json.dumps(payload)}\n\n"
    with _sse_lock:
        dead = []
        for q in _sse_subscribers:
            try:
                q.put_nowait(msg)
            except queue.Full:
                dead.append(q)
        for q in dead:
            _sse_subscribers.remove(q)


# ── Vistas ─────────────────────────────────────────────────────────────────────

@signage_bp.route('/')
@login_required
def index():
    return render_template('signage/index.html')


@signage_bp.route('/display')
def display():
    """Pantalla pública — sin autenticación."""
    return render_template('signage/display.html')


# ── API de datos (solo para el panel, no guarda nada) ─────────────────────────

@signage_bp.route('/data')
@login_required
def data():
    """
    Trae producción + stock de Odoo y los devuelve al panel.
    No guarda nada en el servidor.
    """
    try:
        models, uid = odoo_client.connect()
        orders      = odoo_client.get_active_manufacturing_orders(models, uid)
        raw_cats    = odoo_client.get_manufacturing_totals_by_category(models, uid, orders)

        categorias = {
            cat: [
                {'id': pid, 'name': raw_cats[cat]['names'][pid], 'qty': qty}
                for pid, qty in raw_cats[cat]['total'].items()
            ]
            for cat in ('inyeccion', 'ensamble', 'cepillo')
        }
    except Exception as e:
        return jsonify({'error': f'Error conectando a Odoo: {e}'}), 500

    try:
        low_stock, _ = stock_monitor.get_low_stock_summary()
        low_stock = low_stock or []
    except Exception:
        low_stock = []

    return jsonify({
        'categorias':  categorias,
        'low_stock':   low_stock,
        'stock_total': len(low_stock),
        'now':         datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
    })


# ── Guardar selección → actualizar display ─────────────────────────────────────

@signage_bp.route('/update-display', methods=['POST'])
@login_required
def update_display():
    """
    Recibe los items seleccionados con sus datos (id, name, qty, cat)
    codificados en JSON en el campo 'selected_items'.
    Guarda SOLO esos items en memoria y empuja a display via SSE.
    """
    global _display_cache

    raw = request.form.get('selected_items', '[]')
    try:
        selected_items = json.loads(raw)
    except json.JSONDecodeError:
        selected_items = []

    payload = {
        'items': selected_items,          # [{id, name, qty, cat}, ...]
        'now':   datetime.now().strftime('%d/%m/%Y %H:%M:%S'),
    }

    with _cache_lock:
        _display_cache = payload

    _push_to_displays(payload)
    return redirect(url_for('signage.index'))


# ── SSE — stream para display ──────────────────────────────────────────────────

@signage_bp.route('/events')
def events():
    """
    Server-Sent Events — display se suscribe aquí.
    Al conectar recibe el cache actual (si existe).
    Luego recibe eventos solo cuando el panel guarda una nueva selección.
    """
    q: queue.Queue = queue.Queue(maxsize=5)

    with _sse_lock:
        _sse_subscribers.append(q)

    with _cache_lock:
        initial = _display_cache

    def stream():
        try:
            if initial is not None:
                yield f"data: {json.dumps(initial)}\n\n"
            while True:
                try:
                    msg = q.get(timeout=25)
                    yield msg
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            with _sse_lock:
                if q in _sse_subscribers:
                    _sse_subscribers.remove(q)

    return Response(
        stream_with_context(stream()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control':     'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )


# ── API de stock ───────────────────────────────────────────────────────────────

@signage_bp.route('/check-stock', methods=['POST'])
@login_required
def check_stock():
    force = request.json.get('force', False) if request.is_json else False
    success, message = stock_monitor.check_and_notify(force=force)
    return jsonify({'success': success, 'message': message})


@signage_bp.route('/stock-summary')
@login_required
def stock_summary():
    products, error = stock_monitor.get_low_stock_summary()
    if error:
        return jsonify({'error': error}), 500
    return jsonify({
        'low_stock_products': products,
        'total_count':        len(products) if products else 0,
        'timestamp':          datetime.now().isoformat(),
    })


# ── API de notificaciones ──────────────────────────────────────────────────────

@signage_bp.route('/notification-status')
@login_required
def notification_status():
    return jsonify({
        'email':         bool(os.getenv('EMAIL_USER') and os.getenv('EMAIL_PASSWORD') and os.getenv('EMAIL_RECIPIENTS')),
        'telegram':      bool(os.getenv('TELEGRAM_BOT_TOKEN') and (os.getenv('TELEGRAM_CHAT_IDS') or os.getenv('TELEGRAM_STOCK_RECIPIENTS'))),
        'callmebot':     bool(os.getenv('CALLMEBOT_NUMBERS')),
        'whatsapp_meta': bool(os.getenv('WHATSAPP_TOKEN') and os.getenv('WHATSAPP_PHONE_ID')),
    })


@signage_bp.route('/test-notifications', methods=['POST'])
@login_required
def test_notifications():
    nm        = NotificationManager()
    timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
    text = (
        f'🧪 MENSAJE DE PRUEBA - {timestamp}\n\n'
        '✅ Las notificaciones están funcionando correctamente.\n'
        '📊 El sistema alertará cuando haya productos con stock bajo.'
    )
    html = f"""<html><body>
        <h2 style="color:#2196f3">🧪 MENSAJE DE PRUEBA</h2>
        <p><strong>Fecha:</strong> {timestamp}</p>
        <p>✅ Las notificaciones están funcionando correctamente.</p>
    </body></html>"""
    telegram = (
        f'🧪 <b>MENSAJE DE PRUEBA</b>\n📅 <i>{timestamp}</i>\n\n'
        '✅ Las notificaciones están funcionando correctamente.\n'
        '📊 El sistema alertará cuando haya productos con stock bajo.'
    )
    sent = nm.broadcast(
        subject='🧪 Prueba de Notificaciones PPG',
        text=text, html=html, telegram_text=telegram,
        report_type='stock',
    )
    if sent:
        return jsonify({'success': True,  'message': f'Enviado por: {", ".join(sent)}'})
    return jsonify({'success': False, 'message': 'No se pudo enviar. Verifica la configuración.'})
