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

PRODUCTION_CSV_HEADER = [
    'ID Reporte', 'Nombre', 'Turno', 'Fecha', 'Trabajadores',
    'Maquina 1 Cantidad', 'Maquina 1 Tipo de Cepillo', 'Maquina 1 Color',
    'Maquina 2 Cantidad', 'Maquina 2 Tipo de Cepillo', 'Maquina 2 Color',
    'Maquina 3 Cantidad', 'Maquina 3 Tipo de Cepillo', 'Maquina 3 Color',
    'Ensamble', 'Ensartado', 'Pegado', 'Entregas',
    'Produccion Personal', 'Produccion Maquinas', 'Produccion Total',
    'Produccion por Trabajador',
    'Notas Adicionales', 'Fecha y Hora de Envio',
]

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def get_text(key: str) -> str:
    return STRINGS.get(key, key)


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ── JSON helper (production_details.json se mantiene) ─────────────────────────

def _format_products(data):
    return ', '.join(f'{row[0]}: {row[1]}' for row in data) if data else ''


def _format_deliveries(data):
    return ', '.join(f'{row[0]} - {row[1]}' for row in data) if data else ''


def save_production_details_json(report_id, name, job_shift, date, workers,
                                  timestamp, assembly_data, stringing_data, gluing_data):
    """Guarda el detalle de productos en production_details.json (se mantiene en JSON)."""
    os.makedirs('data', exist_ok=True)
    json_file = 'data/production_details.json'
    detail = {
        'id_reporte':          report_id,
        'nombre':              name,
        'turno':               get_text(job_shift),
        'fecha':               date,
        'trabajadores':        workers,
        'fecha_y_hora_de_envio': timestamp,
        'ensamble':  [{'producto': p[0], 'cantidad': p[1]} for p in assembly_data],
        'ensartado': [{'producto': p[0], 'cantidad': p[1]} for p in stringing_data],
        'pegado':    [{'producto': p[0], 'cantidad': p[1]} for p in gluing_data],
    }
    try:
        with open(json_file, encoding='utf-8') as f:
            records = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        records = []
    records.append(detail)
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def read_production_details_json() -> list:
    try:
        with open('data/production_details.json', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


# ── Constructores de mensajes de notificación ──────────────────────────────────

def build_production_message(report_id, name, job_shift, date, workers,
                              machine_data, assembly_data, stringing_data,
                              gluing_data, delivery_data,
                              total_production, total_machines, production_per_worker,
                              additional_notes, timestamp,
                              report_url: str | None = None) -> str:
    lines = [
        '📋 REPORTE DE PRODUCCIÓN',
        f'🆔 #{report_id}  |  👤 {name}  |  🔄 {get_text(job_shift)}  |  📅 {date}',
        f'👥 {workers} trabajadores',
        f'👷 Personal: {total_production} uds  |  📈 {production_per_worker} uds/trabajador',
    ]
    if total_machines:
        lines.append(f'🔧 Máquinas: {total_machines} uds')
    if machine_data:
        lines.append('   ' + '  '.join(
            f'M{m[0]}: {m[1]} ({get_text(m[2])})' for m in machine_data
        ))
    if assembly_data:
        lines.append('🔩 Ensamble: ' + ', '.join(f'{p} ×{q}' for p, q in assembly_data))
    if stringing_data:
        lines.append('🧵 Ensartado: ' + ', '.join(f'{p} ×{q}' for p, q in stringing_data))
    if gluing_data:
        lines.append('🔗 Pegado: ' + ', '.join(f'{p} ×{q}' for p, q in gluing_data))
    if delivery_data:
        lines.append('🚚 Entregas: ' + ', '.join(f'{c}' for c, *_ in delivery_data))
    if additional_notes:
        lines.append(f'📝 {additional_notes}')
    if report_url:
        lines.append(f'\n🔗 Ver reporte: {report_url}')
    return '\n'.join(lines)


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


def build_production_email_body(report_id, name, job_shift, date, workers,
                                 machine_data, assembly_data, stringing_data,
                                 gluing_data, delivery_data,
                                 total_production, total_machines, production_per_worker,
                                 additional_notes, timestamp,
                                 report_url: str | None = None) -> str:

    total_combined = total_production + total_machines

    # ── Helpers ───────────────────────────────────────────────────────────────
    def kpi(label, value, color):
        return f"""
        <td style="text-align:center; padding:12px 16px;">
            <div style="font-size:1.5rem; font-weight:800; color:{color};">{value}</div>
            <div style="font-size:.72rem; text-transform:uppercase; letter-spacing:.5px;
                        color:#718096; margin-top:3px;">{label}</div>
        </td>"""

    def section_table(title, rows, cols):
        if not rows:
            return ''
        header = ''.join(f'<th style="padding:8px 12px; text-align:left; background:#f7fafc; color:#4a5568; font-size:.8rem; text-transform:uppercase; letter-spacing:.4px;">{c}</th>' for c in cols)
        body   = ''
        for row in rows:
            cells = ''.join(f'<td style="padding:8px 12px; border-bottom:1px solid #edf2f7; font-size:.88rem;">{v}</td>' for v in row)
            body += f'<tr>{cells}</tr>'
        return f"""
        <div style="margin-bottom:24px;">
            <div style="font-weight:700; color:#2d3748; font-size:.95rem; margin-bottom:8px;
                        padding-bottom:6px; border-bottom:2px solid #e2e8f0;">{title}</div>
            <table style="width:100%; border-collapse:collapse;">
                <thead><tr>{header}</tr></thead>
                <tbody>{body}</tbody>
            </table>
        </div>"""

    # ── KPIs ──────────────────────────────────────────────────────────────────
    kpis_html = f"""
    <table style="width:100%; border-collapse:collapse; background:#f7fafc;
                  border-radius:8px; margin-bottom:24px;">
        <tr>
            {kpi('Total', f'{total_combined:,}', '#2b6cb0')}
            {kpi('Personal', f'{total_production:,}', '#276749')}
            {kpi('Máquinas', f'{total_machines:,}', '#c05621')}
            {kpi('Uds/persona', production_per_worker, '#553c9a')}
        </tr>
    </table>"""

    # ── Secciones de productos ─────────────────────────────────────────────────
    machines_section = section_table(
        '🔧 Producción de Máquinas',
        [[f'Máquina {m[0]}', m[1], get_text(m[2]), get_text(m[3])] for m in machine_data],
        ['Máquina', 'Cantidad', 'Tipo', 'Color'],
    ) if machine_data else ''

    assembly_section = section_table(
        '🔩 Ensamble',
        [[p, q] for p, q in assembly_data],
        ['Producto', 'Cantidad'],
    ) if assembly_data else ''

    stringing_section = section_table(
        '🧵 Ensartado',
        [[p, q] for p, q in stringing_data],
        ['Producto', 'Cantidad'],
    ) if stringing_data else ''

    gluing_section = section_table(
        '🔗 Pegado',
        [[p, q] for p, q in gluing_data],
        ['Producto', 'Cantidad'],
    ) if gluing_data else ''

    deliveries_section = section_table(
        '🚚 Entregas',
        [[c, d] for c, d, *_ in delivery_data],
        ['Cliente', 'Producto'],
    ) if delivery_data else ''

    notes_html = f"""
    <div style="background:#fffbeb; border-left:4px solid #f6ad55; padding:12px 16px;
                border-radius:4px; margin-bottom:24px; font-size:.88rem; color:#744210;">
        <strong>📝 Notas:</strong> {additional_notes}
    </div>""" if additional_notes else ''

    link_html = f"""
    <div style="text-align:center; margin:24px 0;">
        <a href="{report_url}"
           style="background:#3182ce; color:#fff; padding:12px 28px; border-radius:6px;
                  text-decoration:none; font-weight:600; font-size:.95rem; display:inline-block;">
            Ver Reporte Completo →
        </a>
    </div>""" if report_url else ''

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"></head>
<body style="margin:0; padding:0; background:#edf2f7; font-family:'Segoe UI',Arial,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#edf2f7; padding:32px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0"
       style="background:#fff; border-radius:10px; overflow:hidden;
              box-shadow:0 2px 8px rgba(0,0,0,.08);">

    <!-- Header -->
    <tr>
        <td style="background:#2b6cb0; padding:24px 32px;">
            <div style="color:#fff; font-size:1.3rem; font-weight:700;">
                📋 Nuevo Reporte de Producción
            </div>
            <div style="color:#bee3f8; font-size:.88rem; margin-top:4px;">
                Plásticos Plasa de Guadalajara
            </div>
        </td>
    </tr>

    <!-- Info general -->
    <tr>
        <td style="padding:24px 32px 0;">
            <table style="width:100%; border-collapse:collapse; font-size:.88rem; color:#4a5568;">
                <tr>
                    <td style="padding:4px 0;"><strong>Reporte #</strong></td>
                    <td style="padding:4px 0;">{report_id}</td>
                    <td style="padding:4px 0;"><strong>Fecha</strong></td>
                    <td style="padding:4px 0;">{date}</td>
                </tr>
                <tr>
                    <td style="padding:4px 0;"><strong>Reportado por</strong></td>
                    <td style="padding:4px 0;">{name}</td>
                    <td style="padding:4px 0;"><strong>Turno</strong></td>
                    <td style="padding:4px 0;">{get_text(job_shift)}</td>
                </tr>
                <tr>
                    <td style="padding:4px 0;"><strong>Trabajadores</strong></td>
                    <td style="padding:4px 0;">{workers}</td>
                    <td style="padding:4px 0;"><strong>Enviado</strong></td>
                    <td style="padding:4px 0;">{timestamp}</td>
                </tr>
            </table>
        </td>
    </tr>

    <!-- KPIs -->
    <tr><td style="padding:20px 32px 0;">{kpis_html}</td></tr>

    <!-- Secciones -->
    <tr>
        <td style="padding:8px 32px 24px;">
            {machines_section}
            {assembly_section}
            {stringing_section}
            {gluing_section}
            {deliveries_section}
            {notes_html}
            {link_html}
        </td>
    </tr>

    <!-- Footer -->
    <tr>
        <td style="background:#f7fafc; padding:16px 32px; text-align:center;
                   font-size:.75rem; color:#a0aec0; border-top:1px solid #e2e8f0;">
            Reporte automático · Plásticos Plasa de Guadalajara
        </td>
    </tr>

</table>
</td></tr>
</table>
</body>
</html>"""
