"""
Blueprint de etiquetas PDF — autenticación de reportes requerida.
Rutas: /etiquetas, /etiquetas/search_clientes, /etiquetas/search_productos
"""

import base64
import logging
import os
from datetime import date
from io import BytesIO

from flask import Blueprint, abort, jsonify, render_template, request, send_file
from PIL import Image
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .odoo_client import OdooClient
from utils import get_text
from auth import login_required as reports_login_required

logger = logging.getLogger(__name__)

# ── Conexión Odoo (mismas vars de entorno que el resto de la app) ──────────────
odoo = OdooClient(
    url      = os.getenv('ODOO_URL',      'http://192.168.1.160:8070/'),
    db       = os.getenv('ODOO_DB',       'ppg'),
    username = os.getenv('ODOO_USERNAME', 'admin'),
    password = os.getenv('ODOO_PASSWORD', 'odooppg'),
)

# Pre-autenticar al cargar el módulo para evitar timeout en la primera request
try:
    _ = odoo._uid
    logger.info('[Labels] Conexión Odoo establecida')
except Exception as e:
    logger.warning(f'[Labels] No se pudo pre-autenticar con Odoo: {e}')

# ── Dimensiones etiqueta ───────────────────────────────────────────────────────
ANCHO_PT = 200 * mm
ALTO_PT  = 102.1 * mm

# ── Blueprint ──────────────────────────────────────────────────────────────────
labels_bp = Blueprint('labels', __name__, url_prefix='/etiquetas')

FIXED_IMG = os.path.join(os.path.dirname(__file__), '..', '..', 'static', 'fixed.png')


# ── PDF ────────────────────────────────────────────────────────────────────────

def _wrap_text(c, text, x, y, max_w, font='Helvetica', size=8, leading=None):
    if not text:
        return y
    if leading is None:
        leading = size + 2
    c.setFont(font, size)
    words, lines, cur = str(text).split(), [], ''
    for w in words:
        test = (cur + ' ' + w).strip()
        if c.stringWidth(test, font, size) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    for i, line in enumerate(lines):
        c.drawString(x, y - i * leading, line)
    return y - len(lines) * leading


def create_label_pdf(data: dict) -> BytesIO:
    buf = BytesIO()
    c   = canvas.Canvas(buf, pagesize=(ANCHO_PT, ALTO_PT))
    pad = 8

    # Encabezado
    hy = ALTO_PT - pad - 5
    c.setFont('Helvetica-Bold', 16)
    c.drawCentredString(ANCHO_PT / 2, hy,
        data.get('header_text', 'Plásticos Plasa de Guadalajara S.A. de C.V.'))
    for txt_key, default in [
        ('empresa_direccion', 'Calle Florentino Acosta #1090'),
        ('empresa_ciudad',    'Guadalajara, Jalisco   C.P.44329'),
        ('empresa_contacto',  'Teléfono: 33-3651-5424    www.plasticosplasa.com'),
    ]:
        hy -= 12
        c.setFont('Helvetica', 8)
        c.drawCentredString(ANCHO_PT / 2, hy, data.get(txt_key, default))

    line_y = ALTO_PT - 0.18 * ALTO_PT
    c.setLineWidth(0.5)
    c.line(pad / 2, line_y, ANCHO_PT - pad / 2, line_y)

    col_w  = [0.30 * ANCHO_PT, 0.30 * ANCHO_PT, 0.40 * ANCHO_PT]
    col_x  = [0, col_w[0], col_w[0] + col_w[1]]
    col_top = line_y - pad
    avail_h = col_top - pad

    # Columna izquierda
    lx, lw = col_x[0] + pad, col_w[0] - 2 * pad
    ly = col_top - 20
    c.setFont('Helvetica-Bold', 18)
    c.drawCentredString(lx + lw / 2, ly, 'FRÁGIL')
    ly -= 12
    c.setFont('Helvetica', 12)
    c.drawCentredString(lx + lw / 2, ly, 'Manejese con Cuidado')
    ly -= 6
    try:
        img = Image.open(FIXED_IMG)
        iw, ih = img.size
        scale  = min(lw / iw, avail_h * 0.6 / ih, 1.0)
        dw, dh = iw * scale, ih * scale
        b = BytesIO(); img.convert('RGBA').save(b, 'PNG'); b.seek(0)
        c.drawImage(ImageReader(b), lx + (lw - dw) / 2, ly - dh,
                    width=dw, height=dh, preserveAspectRatio=True)
        ly -= dh + 5
    except Exception:
        ly -= 20
    c.setFont('Helvetica', 12)
    c.drawCentredString(lx + lw / 2, ly - 10, 'ESTIBA MÁXIMA 3 CAJAS')

    # Columna central
    cx, cw = col_x[1] + pad, col_w[1] - 2 * pad
    cy = col_top - 20
    c.setFont('Helvetica-Bold', 9)
    c.drawString(cx, cy - 8, 'Información del cliente:')
    cy -= 28
    cliente = data.get('cliente', {})
    cy = _wrap_text(c, cliente.get('name', ''), cx, cy, cw, 'Helvetica-Bold', 12, 11)
    cy -= 4
    cy = _wrap_text(c, f"Tel: {cliente.get('phone', '')}", cx, cy, cw, size=8, leading=9)
    cy -= 2
    dir_ = (f"{cliente.get('street','')} {cliente.get('street2','')}, "
            f"{cliente.get('city','')} {cliente.get('zip','')}")
    cy = _wrap_text(c, f'Dirección: {dir_}', cx, cy, cw, size=8, leading=9)
    cy -= 2
    cy = _wrap_text(c, f"Email: {cliente.get('email','')}", cx, cy, cw, size=8, leading=9)
    cy -= 20
    c.setFont('Helvetica-Bold', 9)
    c.drawString(cx, cy, 'Detalles del Embarque:')
    cy -= 14
    c.setFont('Helvetica', 8)
    c.drawString(cx, cy, f'Fecha: {date.today().strftime("%d/%m/%Y")}')
    cy -= 12
    for label, val in [
        ('Lote',          date.today().strftime('%y%m%d')),
        ('Cantidad',      data.get('cantidad', '')),
        ('Peso bruto',    data.get('peso_bruto', '')),
        ('Peso neto',     data.get('peso_neto', '')),
        ('Peso unitario', data.get('peso_unitario', '')),
    ]:
        cy = _wrap_text(c, f'{label}: {val}', cx, cy, cw, size=8, leading=10)

    # Columna derecha
    rx, rw = col_x[2] + pad, col_w[2] - 2 * pad
    ry = col_top - 20
    producto = data.get('producto', {})
    ry = _wrap_text(c, producto.get('display_name', ''), rx, ry, rw,
                    'Helvetica-Bold', 12, 14)
    ry -= 6
    img_b64 = producto.get('image_1920')
    if img_b64:
        try:
            img = Image.open(BytesIO(base64.b64decode(img_b64))).convert('RGBA')
            iw, ih = img.size
            scale  = min(rw / iw, avail_h * 0.7 / ih, 1.0)
            dw, dh = iw * scale, ih * scale
            b = BytesIO(); img.save(b, 'PNG'); b.seek(0)
            c.drawImage(ImageReader(b), rx, ry - dh,
                        width=dw, height=dh, preserveAspectRatio=True)
        except Exception:
            logger.exception('Error procesando imagen del producto')

    # Pie
    c.setFont('Helvetica-Oblique', 6)
    c.drawCentredString(ANCHO_PT / 2, pad / 2,
        data.get('footer_text', 'Generado por Plásticos Plasa - Etiqueta personalizada'))

    c.showPage()
    c.save()
    buf.seek(0)
    return buf


# ── Rutas ──────────────────────────────────────────────────────────────────────

@labels_bp.route('/', methods=['GET', 'POST'])
@reports_login_required
def label():
    if request.method == 'POST':
        try:
            cliente_id  = int(request.form.get('cliente', 0))
            producto_id = int(request.form.get('producto', 0))
        except ValueError:
            abort(400, 'Cliente o producto inválido')

        cliente  = odoo.get_partner(cliente_id)
        producto = odoo.get_product(producto_id)
        if not cliente or not producto:
            abort(404, 'Cliente o producto no encontrado')

        # Sobrescrituras opcionales
        if request.form.get('cliente_name'):    cliente['name']    = request.form['cliente_name']
        if request.form.get('cliente_phone'):   cliente['phone']   = request.form['cliente_phone']
        if request.form.get('cliente_address'):
            cliente.update({'street': request.form['cliente_address'],
                            'street2': '', 'city': '', 'zip': ''})
        if request.form.get('cliente_email'):   cliente['email']   = request.form['cliente_email']
        if request.form.get('producto_name'):   producto['display_name'] = request.form['producto_name']
        if 'producto_image' in request.files:
            f = request.files['producto_image']
            if f and f.filename:
                producto['image_1920'] = base64.b64encode(f.read()).decode('utf-8')

        label_data = {
            'cliente':           cliente,
            'producto':          producto,
            'cantidad':          request.form.get('cantidad', ''),
            'peso_bruto':        request.form.get('peso_bruto', ''),
            'peso_neto':         request.form.get('peso_neto', ''),
            'peso_unitario':     request.form.get('peso_unitario', ''),
            'header_text':       request.form.get('header_text', ''),
            'empresa_direccion': request.form.get('empresa_direccion', ''),
            'empresa_ciudad':    request.form.get('empresa_ciudad', ''),
            'empresa_contacto':  request.form.get('empresa_contacto', ''),
            'footer_text':       request.form.get('footer_text', ''),
        }

        try:
            pdf = create_label_pdf(label_data)
            return send_file(pdf, as_attachment=True,
                             download_name='etiqueta.pdf',
                             mimetype='application/pdf')
        except Exception:
            logger.exception('Error generando PDF')
            abort(500, 'Error generando PDF')

    return render_template('labels/label.html', get_text=get_text)


@labels_bp.route('/search_clientes')
@reports_login_required
def search_clientes():
    q = request.args.get('q', '').strip()
    # Sin query → devuelve todos (hasta 200) para la lista inicial
    if not q:
        return jsonify(odoo.search_partners('', limit=200))
    return jsonify(odoo.search_partners(q))


@labels_bp.route('/search_productos')
@reports_login_required
def search_productos():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify(odoo.search_products('', limit=200))
    return jsonify(odoo.search_products(q))
