"""
Utilidades compartidas — PPG Unified
"""
import csv
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
    'Produccion Total', 'Produccion por Trabajador',
    'Notas Adicionales', 'Fecha y Hora de Envio',
]

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}


def get_text(key: str) -> str:
    return STRINGS.get(key, key)


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ── CSV / JSON helpers ─────────────────────────────────────────────────────────

def _format_products(data):
    return ', '.join(f'{row[0]}: {row[1]}' for row in data) if data else ''


def _format_deliveries(data):
    return ', '.join(f'{row[0]} - {row[1]}' for row in data) if data else ''


def get_next_report_id(report_type: str = 'production') -> int:
    csv_file = f'data/{report_type}_reports.csv'
    try:
        with open(csv_file, encoding='utf-8') as f:
            return len(list(csv.reader(f)))
    except FileNotFoundError:
        return 1


def save_production_report(report_id, name, job_shift, date, workers, additional_notes,
                            timestamp, machine_data, assembly_data, stringing_data,
                            gluing_data, delivery_data, total_production, production_per_worker):
    csv_file   = 'data/production_reports.csv'
    file_exists = os.path.isfile(csv_file)
    machines   = {str(m[0]): m for m in machine_data}

    def machine_fields(num):
        m = machines.get(str(num))
        return [m[1], get_text(m[2]), get_text(m[3])] if m else ['', '', '']

    row = [
        report_id, name, get_text(job_shift), date, workers,
        *machine_fields(1), *machine_fields(2), *machine_fields(3),
        _format_products(assembly_data),
        _format_products(stringing_data),
        _format_products(gluing_data),
        _format_deliveries(delivery_data),
        total_production, production_per_worker,
        additional_notes, timestamp,
    ]

    with open(csv_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(PRODUCTION_CSV_HEADER)
        writer.writerow(row)

    # JSON detallado
    json_file = 'data/production_details.json'
    detail = {
        'id_reporte': report_id, 'nombre': name,
        'turno': get_text(job_shift), 'fecha': date,
        'trabajadores': workers, 'fecha_y_hora_de_envio': timestamp,
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


def save_report(data, report_type: str):
    csv_file   = f'data/{report_type}_reports.csv'
    file_exists = os.path.isfile(csv_file)
    with open(csv_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['Report_ID', 'Type', 'Item_Name', 'Location',
                             'Failure_Description', 'Additional_Info', 'Photo_Path', 'Timestamp'])
        writer.writerow(data)


# ── Constructores de mensajes de notificación ──────────────────────────────────

def build_production_message(report_id, name, job_shift, date, workers,
                              machine_data, assembly_data, stringing_data,
                              gluing_data, delivery_data,
                              total_production, production_per_worker,
                              additional_notes, timestamp) -> str:
    lines = [
        '📋 REPORTE DE PRODUCCIÓN',
        f'🆔 Reporte #{report_id}',
        f'👤 {name}  |  🔄 {get_text(job_shift)}  |  📅 {date}',
        f'👥 Trabajadores: {workers}',
        '',
        f'📊 Producción total: {total_production} uds',
        f'📈 Por trabajador: {production_per_worker} uds/trabajador',
    ]
    if machine_data:
        lines.append('\n🔧 Máquinas:')
        for m in machine_data:
            lines.append(f'  • Máq {m[0]}: {m[1]} uds — {get_text(m[2])} {get_text(m[3])}')
    if assembly_data:
        lines.append('\n🔩 Ensamble:')
        for p, q in assembly_data:
            lines.append(f'  • {p}: {q}')
    if stringing_data:
        lines.append('\n🧵 Ensartado:')
        for p, q in stringing_data:
            lines.append(f'  • {p}: {q}')
    if gluing_data:
        lines.append('\n🔗 Pegado:')
        for p, q in gluing_data:
            lines.append(f'  • {p}: {q}')
    if delivery_data:
        lines.append('\n🚚 Entregas:')
        for customer, desc, *_ in delivery_data:
            lines.append(f'  • {customer}: {desc}')
    if additional_notes:
        lines.append(f'\n📝 Notas: {additional_notes}')
    lines.append(f'\n🕐 {timestamp}')
    return '\n'.join(lines)


def build_simple_message(report_id, report_type: str, item_name: str,
                          failure_description: str, timestamp: str) -> str:
    tipo = {'personal': 'Personal', 'company': 'Empresa'}.get(report_type, report_type.title())
    return (
        f'📋 REPORTE {tipo.upper()}\n'
        f'🆔 Reporte #{report_id}\n'
        f'📌 {item_name}\n'
        f'📝 {failure_description}\n'
        f'🕐 {timestamp}'
    )


def build_production_email_body(report_id, name, job_shift, date, workers,
                                 machine_data, assembly_data, stringing_data,
                                 gluing_data, delivery_data,
                                 total_production, production_per_worker,
                                 additional_notes, timestamp) -> str:
    def section(title, rows):
        if not rows:
            return ''
        lines = [f'\n--- {title} ---']
        lines += [f'• {r}' for r in rows]
        return '\n'.join(lines)

    machines_rows = [
        f'Maquina {m[0]}: {m[1]} unidades - {get_text(m[2])} {get_text(m[3])}'
        for m in machine_data
    ] if machine_data else []

    return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                           REPORTE DE PRODUCCION                              ║
╚══════════════════════════════════════════════════════════════════════════════╝

📋 INFORMACION GENERAL
• ID del Reporte: {report_id}
• Reportado por: {name}
• Turno: {get_text(job_shift)}
• Fecha: {date}
• Trabajadores en turno: {workers}
• Fecha y hora de envio: {timestamp}

📊 RESUMEN DE PRODUCCION
• Produccion Total: {total_production} unidades
• Produccion por Trabajador: {production_per_worker} unidades/trabajador
{section('PRODUCCION DE MAQUINAS', machines_rows)}
{section('ENSAMBLE', [f'{p}: {q} unidades' for p, q in assembly_data])}
{section('ENSARTADO', [f'{p}: {q} unidades' for p, q in stringing_data])}
{section('PEGADO', [f'{p}: {q} unidades' for p, q in gluing_data])}
{section('ENTREGAS', [f'Cliente: {c}  Producto: {d}' for c, d, *_ in delivery_data])}
{section('NOTAS ADICIONALES', [additional_notes]) if additional_notes else ''}
═══════════════════════════════════════════════════════════════════════════════

Este es un reporte automatico del sistema de Plasticos Plasa de Guadalajara.
"""
