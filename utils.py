"""
Utilidades compartidas — PPG Unified
"""
import json
import os

# ── Strings de UI ──────────────────────────────────────────────────────────────

STRINGS = {
    'title': 'Plasticos Plasa de Guadalajara',
    'personal_report': 'Reporte Personal',
    'company_report': 'Reporte de Empresa',
    'production_report': 'Reporte de Produccion',
    'personal_desc': 'Para problemas individuales de trabajadores',
    'company_desc': 'Para problemas de equipos/maquinaria con subida de fotos',
    'production_desc': 'Para reportar datos de produccion diaria',
    'item_name': 'Nombre del Articulo',
    'topic': 'Tema',
    'description': 'Descripcion',
    'location': 'Ubicacion',
    'failure_description': 'Descripcion de la Falla',
    'additional_info': 'Informacion Adicional',
    'photo': 'Foto',
    'submit': 'Enviar Reporte',
    'back': 'Volver',
    'success_msg': 'Reporte #{} enviado exitosamente!',
    'name': 'Nombre de Quien Reporta',
    'job_shift': 'Turno de Trabajo',
    'date': 'Fecha',
    'quantity_persons': 'Cantidad de Personas que Trabajaron en el Turno',
    'mascara_brush_production': 'Produccion de Cepillos',
    'machine_1': 'Maquina 1',
    'machine_2': 'Maquina 2',
    'machine_3': 'Maquina 3',
    'quantity': 'Cantidad',
    'brush_type': 'Tipo de Cepillo',
    'color': 'Color',
    'general': 'General',
    'general_description': 'Descripcion General',
    'assembly_production': 'Ensamble',
    'search_product': 'Buscar Producto',
    'select_product': 'Seleccionar Producto',
    'assembled_quantity': 'Cantidad Ensamblada',
    'add_product': 'Agregar Producto',
    'selected_products': 'Productos Seleccionados',
    'no_products_selected': 'No hay productos seleccionados',
    'select_product_alert': 'Por favor selecciona un producto',
    'enter_quantity_alert': 'Por favor ingresa una cantidad valida',
    'deliveries': 'Entregas',
    'search_customer': 'Buscar Cliente',
    'select_customer': 'Seleccionar Cliente',
    'delivery_description': 'Descripcion del Producto a Entregar',
    'add_delivery': 'Agregar Entrega',
    'selected_deliveries': 'Entregas Seleccionadas',
    'no_deliveries_selected': 'No hay entregas seleccionadas',
    'select_customer_alert': 'Por favor selecciona un cliente',
    'enter_description_alert': 'Por favor ingresa una descripcion',
    'additional_notes': 'Notas Adicionales',
    'additional_notes_description': 'Informacion adicional o notas importantes',
    'additional_notes_placeholder': 'Ingresa cualquier informacion adicional, observaciones o notas importantes del turno...',
    'morning': 'Matutino',
    'afternoon': 'Vespertino',
    'night': 'Nocturno',
    'straight': 'Recto',
    'spiral': 'Espiral',
    'bullet': 'Bala',
    'mini_bullet': 'Balita',
    'pine': 'Pino',
    'peanut': 'Cacahuate',
    'balloon': 'Globo',
    'black': 'Negro',
    'brown': 'Cafe',
    'blue': 'Azul',
    'green': 'Verde',
    'turquoise': 'Turquesa',
    'pink': 'Rosa',
    'purple': 'Morado',
    'transparent': 'Transparente',
}

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def get_text(key: str) -> str:
    return STRINGS.get(key, key)


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ── Helpers de formato ─────────────────────────────────────────────────────────

def _format_products(data):
    return ', '.join(f'{row[0]}: {row[1]}' for row in data) if data else ''


def _format_deliveries(data):
    return ', '.join(f'{row[0]} - {row[1]}' for row in data) if data else ''


# ── JSON de detalles de producción ─────────────────────────────────────────────

def save_production_details_json(report_id, name, job_shift, date, workers,
                                  timestamp, section_data: dict,
                                  update_existing: bool = False):
    """Guarda o actualiza el detalle de productos en production_details.json.
    section_data: {'ensamble': [[name, qty], ...], 'pegado': [...], ...}
    """
    from blueprints.reports.production_sections import PRODUCTION_SECTIONS
    os.makedirs('data', exist_ok=True)
    json_file = 'data/production_details.json'
    detail = {
        'id_reporte':            report_id,
        'nombre':                name,
        'turno':                 get_text(job_shift),
        'fecha':                 date,
        'trabajadores':          workers,
        'fecha_y_hora_de_envio': timestamp,
    }
    for s in PRODUCTION_SECTIONS:
        data = section_data.get(s['key'], [])
        detail[s['json_key']] = [{'producto': p[0], 'cantidad': p[1]} for p in data]

    try:
        with open(json_file, encoding='utf-8') as f:
            records = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        records = []

    if update_existing:
        replaced = False
        for i, r in enumerate(records):
            if str(r.get('id_reporte')) == str(report_id):
                records[i] = detail
                replaced = True
                break
        if not replaced:
            records.append(detail)
    else:
        records.append(detail)

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def read_production_details_json() -> list:
    try:
        with open('data/production_details.json', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# ── Mensajes de notificación ───────────────────────────────────────────────────

def build_simple_message(report_id, report_type: str, item_name: str,
                          failure_description: str, timestamp: str,
                          report_url: str | None = None) -> str:
    tipo = {'personal': 'Personal', 'company': 'Empresa'}.get(report_type, report_type.title())
    lines = [
        f'📋 REPORTE {tipo.upper()}',
        f'🆔 #{report_id}  |  📌 {item_name}',
        f'📝 {failure_description}',
    ]
    if report_url:
        lines.append(f'\n🔗 Ver reporte: {report_url}')
    return '\n'.join(lines)


def build_production_email_body_from_db(report: dict,
                                         report_url: str | None = None) -> str:
    """
    Construye el email HTML de notificación leyendo directamente
    del dict que devuelve get_production_report_by_id().

    Flujo: guardar en DB → leer de DB → llamar esta función → enviar.
    """
    from blueprints.reports.production_sections import PRODUCTION_SECTIONS
    from database import parse_maquinas

    report_id              = report['id']
    name                   = report['nombre']
    turno                  = report['turno']
    date                   = report['fecha']
    workers                = report['trabajadores']
    timestamp              = report['timestamp']
    total_production       = report['produccion_personal']
    total_machines         = report['produccion_maquinas']
    total_combined         = report['produccion_total']
    production_per_hour    = report['produccion_por_persona_hora']
    additional_notes       = report.get('notas', '')
    entregas_str           = report.get('entregas', '')

    # Máquinas desde columna JSON (con fallback a columnas viejas)
    machine_rows = []
    for m in parse_maquinas(report):
        machine_rows.append([f'Máquina {m["maquina"]}', m['cantidad'], m['tipo'], m['color']])

    # ── Helpers HTML ──────────────────────────────────────────────────────────
    def kpi(label, value, color):
        return f"""<td style="text-align:center; padding:12px 16px;">
            <div style="font-size:1.5rem; font-weight:800; color:{color};">{value}</div>
            <div style="font-size:.72rem; text-transform:uppercase; letter-spacing:.5px;
                        color:#718096; margin-top:3px;">{label}</div>
        </td>"""

    def section_table(title, rows, cols):
        if not rows:
            return ''
        header = ''.join(
            f'<th style="padding:8px 12px; text-align:left; background:#f7fafc; '
            f'color:#4a5568; font-size:.8rem; text-transform:uppercase;">{c}</th>'
            for c in cols
        )
        body = ''.join(
            '<tr>' + ''.join(
                f'<td style="padding:8px 12px; border-bottom:1px solid #edf2f7; font-size:.88rem;">{v}</td>'
                for v in row
            ) + '</tr>'
            for row in rows
        )
        return f"""<div style="margin-bottom:24px;">
            <div style="font-weight:700; color:#2d3748; font-size:.95rem; margin-bottom:8px;
                        padding-bottom:6px; border-bottom:2px solid #e2e8f0;">{title}</div>
            <table style="width:100%; border-collapse:collapse;">
                <thead><tr>{header}</tr></thead>
                <tbody>{body}</tbody>
            </table>
        </div>"""

    kpis_html = f"""<table style="width:100%; border-collapse:collapse; background:#f7fafc;
                  border-radius:8px; margin-bottom:24px;"><tr>
        {kpi('Total', f'{total_combined:,}', '#2b6cb0')}
        {kpi('Personal', f'{total_production:,}', '#276749')}
        {kpi('Máquinas', f'{total_machines:,}', '#c05621')}
        {kpi('Uds/persona/hora', production_per_hour, '#553c9a')}
    </tr></table>"""

    machines_html = section_table('🔧 Producción de Máquinas', machine_rows,
                                   ['Máquina', 'Cantidad', 'Tipo', 'Color'])

    # Secciones dinámicas — leer directamente de las columnas de la DB
    sections_html = ''
    for s in PRODUCTION_SECTIONS:
        raw = report.get(s['key'], '') or ''
        if not raw:
            continue
        # Formato almacenado: "Producto A: 10, Producto B: 5"
        rows = []
        for item in raw.split(', '):
            if ': ' in item:
                prod, qty = item.split(': ', 1)
                rows.append([prod.strip(), qty.strip()])
        sections_html += section_table(s['label'], rows, ['Producto', 'Cantidad'])

    # Entregas
    deliveries_html = ''
    if entregas_str:
        rows = []
        for item in entregas_str.split(', '):
            if ' - ' in item:
                cliente, desc = item.split(' - ', 1)
                rows.append([cliente.strip(), desc.strip()])
        deliveries_html = section_table('🚚 Entregas', rows, ['Cliente', 'Producto'])

    notes_html = f"""<div style="background:#fffbeb; border-left:4px solid #f6ad55;
                padding:12px 16px; border-radius:4px; margin-bottom:24px;
                font-size:.88rem; color:#744210;">
        <strong>📝 Notas:</strong> {additional_notes}
    </div>""" if additional_notes else ''

    link_html = f"""<div style="text-align:center; margin:24px 0;">
        <a href="{report_url}" style="background:#3182ce; color:#fff; padding:12px 28px;
           border-radius:6px; text-decoration:none; font-weight:600; font-size:.95rem;
           display:inline-block;">Ver Reporte Completo →</a>
    </div>""" if report_url else ''

    return f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="UTF-8"></head>
<body style="margin:0; padding:0; background:#edf2f7; font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#edf2f7; padding:32px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0"
       style="background:#fff; border-radius:10px; overflow:hidden; box-shadow:0 2px 8px rgba(0,0,0,.08);">
    <tr><td style="background:#2b6cb0; padding:24px 32px;">
        <div style="color:#fff; font-size:1.3rem; font-weight:700;">📋 Nuevo Reporte de Producción</div>
        <div style="color:#bee3f8; font-size:.88rem; margin-top:4px;">Plásticos Plasa de Guadalajara</div>
    </td></tr>
    <tr><td style="padding:24px 32px 0;">
        <table style="width:100%; border-collapse:collapse; font-size:.88rem; color:#4a5568;">
            <tr>
                <td style="padding:4px 0;"><strong>Reporte #</strong></td><td>{report_id}</td>
                <td style="padding:4px 0;"><strong>Fecha</strong></td><td>{date}</td>
            </tr>
            <tr>
                <td style="padding:4px 0;"><strong>Reportado por</strong></td><td>{name}</td>
                <td style="padding:4px 0;"><strong>Turno</strong></td><td>{turno}</td>
            </tr>
            <tr>
                <td style="padding:4px 0;"><strong>Trabajadores</strong></td><td>{workers}</td>
                <td style="padding:4px 0;"><strong>Enviado</strong></td><td>{timestamp}</td>
            </tr>
        </table>
    </td></tr>
    <tr><td style="padding:20px 32px 0;">{kpis_html}</td></tr>
    <tr><td style="padding:8px 32px 24px;">
        {machines_html}{sections_html}{deliveries_html}{notes_html}{link_html}
    </td></tr>
    <tr><td style="background:#f7fafc; padding:16px 32px; text-align:center;
               font-size:.75rem; color:#a0aec0; border-top:1px solid #e2e8f0;">
        Reporte automático · Plásticos Plasa de Guadalajara
    </td></tr>
</table>
</td></tr></table>
</body></html>"""
