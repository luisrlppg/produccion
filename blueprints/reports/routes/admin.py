import io
import json
import os
from collections import defaultdict

from flask import (Blueprint, Response, current_app, flash, redirect,
                   render_template, request, send_from_directory, url_for)

from auth import login_required
from database import (get_production_reports, get_production_dates,
                      get_all_production_reports, get_simple_reports,
                      export_production_csv, export_simple_csv,
                      get_production_report_by_id, update_production_report,
                      delete_production_report)
from utils import (get_text, read_production_details_json,
                   _format_products, _format_deliveries,
                   save_production_details_json)

admin_bp = Blueprint('panel', __name__)

# Horas por turno (mismo mapa que production.py)
_SHIFT_HOURS = {'Matutino': 8.0, 'Vespertino': 7.5, 'Nocturno': 8.0}

def _shift_hours_for_shift(turno: str) -> float:
    return _SHIFT_HOURS.get(turno, 8.0)


# ── Vistas ─────────────────────────────────────────────────────────────────────

@admin_bp.route('/panel/production/view')
@admin_bp.route('/panel/production/stats')
@admin_bp.route('/panel/production')
@admin_bp.route('/panel')
def legacy_redirect():
    return redirect(url_for('reportes'), 301)


@admin_bp.route('/reportes/vista')
@login_required
def production_view():
    selected_date   = request.args.get('date', '')
    available_dates = get_production_dates()
    json_reports    = read_production_details_json()

    filtered = []
    if selected_date:
        for r in get_production_reports(fecha=selected_date):
            json_d = next(
                (j for j in json_reports if str(j.get('id_reporte')) == str(r['id'])),
                None,
            )
            filtered.append({'csv': _db_row_to_csv_dict(r), 'json': json_d})

    return render_template('reports/panel_production_view.html',
        reports=filtered, selected_date=selected_date,
        available_dates=available_dates, get_text=get_text)


@admin_bp.route('/reportes/stats')
@login_required
def production_stats():
    reports      = get_all_production_reports()
    json_reports = read_production_details_json()

    if not reports:
        return render_template('reports/panel_production_stats.html',
                               stats=None, get_text=get_text)

    def _int(val, default=0):
        try:
            return int(val or 0)
        except (ValueError, TypeError):
            return default

    def _float(val, default=0.0):
        try:
            return float(val or 0)
        except (ValueError, TypeError):
            return default

    total_reports     = len(reports)
    total_production  = sum(_int(r['produccion_personal'])  for r in reports)
    total_machines    = sum(_int(r['produccion_maquinas'])  for r in reports)
    total_combined    = sum(_int(r['produccion_total'])     for r in reports)
    total_workers_sum = sum(_int(r['trabajadores'])         for r in reports)
    avg_workers       = round(total_workers_sum / total_reports, 1) if total_reports else 0

    efficiencies = [_float(r['produccion_por_persona_hora']) for r in reports
                    if _float(r['produccion_por_persona_hora']) > 0]
    avg_efficiency  = round(sum(efficiencies) / len(efficiencies), 2) if efficiencies else 0
    best_efficiency = max(efficiencies) if efficiencies else 0

    by_date = defaultdict(lambda: {'total': 0, 'machines': 0, 'workers': 0, 'reports': 0})
    for r in reports:
        d = r.get('fecha', '')
        if not d:
            continue
        by_date[d]['total']    += _int(r['produccion_personal'])
        by_date[d]['machines'] += _int(r['produccion_maquinas'])
        by_date[d]['workers']  += _int(r['trabajadores'])
        by_date[d]['reports']  += 1

    dates_sorted     = sorted(by_date.keys())
    chart_dates      = dates_sorted[-30:]
    chart_production = [by_date[d]['total']   for d in chart_dates]
    chart_workers    = [by_date[d]['workers'] for d in chart_dates]
    chart_efficiency = [
        round(by_date[d]['total'] / (by_date[d]['workers'] * 8.0), 2)
        if by_date[d]['workers'] else 0
        for d in chart_dates
    ]

    by_shift = defaultdict(lambda: {'total': 0, 'machines': 0, 'reports': 0, 'workers': 0})
    for r in reports:
        shift = r.get('turno', 'Desconocido')
        by_shift[shift]['total']    += _int(r['produccion_personal'])
        by_shift[shift]['machines'] += _int(r['produccion_maquinas'])
        by_shift[shift]['reports']  += 1
        by_shift[shift]['workers']  += _int(r['trabajadores'])

    shift_order = ['Matutino', 'Vespertino', 'Nocturno']
    shifts_data = []
    for s in shift_order:
        if s in by_shift:
            d = by_shift[s]
            shifts_data.append({
                'name':              s,
                'total':             d['total'],
                'machines':          d['machines'],
                'reports':           d['reports'],
                'avg_per_hour': round(d['total'] / (d['workers'] * _shift_hours_for_shift(s)), 2)
                                if d['workers'] else 0,
            })
    for s, d in by_shift.items():
        if s not in shift_order:
            shifts_data.append({
                'name':              s,
                'total':             d['total'],
                'machines':          d['machines'],
                'reports':           d['reports'],
                'avg_per_hour': round(d['total'] / (d['workers'] * _shift_hours_for_shift(s)), 2)
                                if d['workers'] else 0,
            })

    shifts_names  = [s['name']  for s in shifts_data]
    shifts_totals = [s['total'] for s in shifts_data]

    product_totals = defaultdict(lambda: {'ensamble': 0, 'ensartado': 0, 'pegado': 0, 'total': 0})
    for jr in json_reports:
        for op in ('ensamble', 'ensartado', 'pegado'):
            for item in jr.get(op, []):
                name = item.get('producto', '').strip()
                qty  = _int(item.get('cantidad', 0))
                if name and qty > 0:
                    product_totals[name][op]    += qty
                    product_totals[name]['total'] += qty

    _best  = max(by_date.items(), key=lambda x: x[1]['total']) if by_date else None
    _worst = min(
        ((d, v) for d, v in by_date.items() if v['total'] > 0),
        key=lambda x: x[1]['total'],
        default=None,
    )
    best_day  = (_best[0],  dict(_best[1]))  if _best  else None
    worst_day = (_worst[0], dict(_worst[1])) if _worst else None

    top_products = [
        {'name': name, 'total': data['total'], 'ensamble': data['ensamble'],
         'ensartado': data['ensartado'], 'pegado': data['pegado']}
        for name, data in sorted(product_totals.items(), key=lambda x: x[1]['total'], reverse=True)[:10]
    ]

    brush_type_totals  = defaultdict(int)
    brush_color_totals = defaultdict(int)
    for r in reports:
        for i in range(1, 4):
            qty   = _int(r.get(f'maquina{i}_cantidad', 0))
            btype = (r.get(f'maquina{i}_tipo') or '').strip()
            color = (r.get(f'maquina{i}_color') or '').strip()
            if qty > 0:
                if btype:
                    brush_type_totals[btype] += qty
                if color:
                    brush_color_totals[color] += qty

    brush_types  = sorted(brush_type_totals.items(),  key=lambda x: x[1], reverse=True)
    brush_colors = sorted(brush_color_totals.items(), key=lambda x: x[1], reverse=True)

    recent = sorted(reports, key=lambda x: x.get('timestamp', ''), reverse=True)[:5]
    # Convertir a formato compatible con el template
    recent_fmt = [_db_row_to_csv_dict(r) for r in recent]

    stats = {
        'total_reports':       total_reports,
        'total_production':    total_production,
        'total_machines':      total_machines,
        'total_combined':      total_combined,
        'avg_workers':         avg_workers,
        'avg_efficiency':      avg_efficiency,
        'best_efficiency':     best_efficiency,
        'chart_dates':         chart_dates,
        'chart_production':    chart_production,
        'chart_workers':       chart_workers,
        'chart_efficiency':    chart_efficiency,
        'shifts_data':         shifts_data,
        'shifts_names':        shifts_names,
        'shifts_totals':       shifts_totals,
        'top_products':        top_products,
        'top_products_names':  [p['name']  for p in top_products],
        'top_products_totals': [p['total'] for p in top_products],
        'brush_types':         brush_types,
        'brush_types_names':   [t for t, _ in brush_types],
        'brush_types_values':  [v for _, v in brush_types],
        'brush_colors':        brush_colors,
        'brush_colors_names':  [c for c, _ in brush_colors],
        'brush_colors_values': [v for _, v in brush_colors],
        'best_day':            best_day,
        'worst_day':           worst_day,
        'recent':              recent_fmt,
    }

    return render_template('reports/panel_production_stats.html',
                           stats=stats, get_text=get_text)


# ── Editar reporte ─────────────────────────────────────────────────────────────

@admin_bp.route('/reportes/editar/<int:report_id>', methods=['GET', 'POST'])
@login_required
def edit_report(report_id):
    report = get_production_report_by_id(report_id)
    if not report:
        flash('Reporte no encontrado', 'error')
        return redirect(url_for('reportes'))

    if request.method == 'POST':
        import json as _json
        from utils import get_text as _gt

        name             = request.form['name'].strip()
        job_shift        = request.form['job_shift'].strip()
        date             = request.form['date'].strip()
        quantity_persons = int(request.form['quantity_persons'].strip())
        additional_notes = request.form.get('additional_notes', '').strip()

        # Máquinas
        machine_data = []
        for i in range(1, 4):
            qty        = request.form.get(f'machine{i}_quantity', '').strip()
            brush_type = request.form.get(f'machine{i}_brush_type', '').strip()
            color      = request.form.get(f'machine{i}_color', '').strip()
            if qty:
                machine_data.append([i, qty, brush_type, color])

        def _parse_json_field(field):
            raw = request.form.get(field, '')
            if not raw:
                return []
            try:
                return [[p['name'], p['quantity']] for p in _json.loads(raw)]
            except (_json.JSONDecodeError, KeyError):
                return []

        assembly_data  = _parse_json_field('assembly_products')
        stringing_data = _parse_json_field('stringing_products')
        gluing_data    = _parse_json_field('gluing_products')

        delivery_data = []
        raw = request.form.get('deliveries', '')
        if raw:
            try:
                delivery_data = [[d['customer'], d['description'], d.get('quantity', 1)]
                                 for d in _json.loads(raw)]
            except (_json.JSONDecodeError, KeyError):
                pass

        def _sum(data):
            total = 0
            for row in data:
                try:
                    total += int(row[1])
                except (ValueError, IndexError):
                    pass
            return total

        total_production = _sum(assembly_data) + _sum(stringing_data) + _sum(gluing_data)
        try:
            total_machines = sum(int(m[1]) for m in machine_data)
        except (ValueError, IndexError):
            total_machines = 0
        from blueprints.reports.routes.production import _shift_hours
        hours = _shift_hours(job_shift)
        try:
            production_per_person_hour = round(total_production / (quantity_persons * hours), 2)
        except ZeroDivisionError:
            production_per_person_hour = 0

        machines = {str(m[0]): m for m in machine_data}
        def mf(num):
            m = machines.get(str(num))
            return (int(m[1]), _gt(m[2]), _gt(m[3])) if m else (0, '', '')

        m1, m2, m3 = mf(1), mf(2), mf(3)

        update_production_report(
            report_id,
            nombre=name,
            turno=_gt(job_shift),
            fecha=date,
            trabajadores=quantity_persons,
            maquina1_cantidad=m1[0], maquina1_tipo=m1[1], maquina1_color=m1[2],
            maquina2_cantidad=m2[0], maquina2_tipo=m2[1], maquina2_color=m2[2],
            maquina3_cantidad=m3[0], maquina3_tipo=m3[1], maquina3_color=m3[2],
            ensamble=_format_products(assembly_data),
            ensartado=_format_products(stringing_data),
            pegado=_format_products(gluing_data),
            entregas=_format_deliveries(delivery_data),
            produccion_personal=total_production,
            produccion_maquinas=total_machines,
            produccion_total=total_production + total_machines,
            produccion_por_persona_hora=production_per_person_hour,
            notas=additional_notes,
        )

        # Actualizar JSON de detalles
        save_production_details_json(
            report_id, name, job_shift, date, quantity_persons,
            report['timestamp'], assembly_data, stringing_data, gluing_data,
            update_existing=True,
        )

        flash(f'Reporte #{report_id} actualizado correctamente', 'success')
        return redirect(url_for('panel.production_view', date=date))

    # GET — pre-llenar el formulario con datos existentes
    return render_template('reports/edit_production.html',
                           report=report, get_text=get_text)


# ── Eliminar reporte (solo admin) ──────────────────────────────────────────────

@admin_bp.route('/reportes/eliminar/<int:report_id>', methods=['POST'])
@login_required
def delete_report(report_id):
    admin_password = os.getenv('ADMIN_PASSWORD', '')
    provided       = request.form.get('admin_password', '')

    if not admin_password or provided != admin_password:
        flash('Contraseña de administrador incorrecta', 'error')
        return redirect(request.referrer or url_for('panel.production_view'))

    report = get_production_report_by_id(report_id)
    if not report:
        flash('Reporte no encontrado', 'error')
        return redirect(url_for('panel.production_view'))

    date = report['fecha']
    delete_production_report(report_id)

    # Eliminar del JSON de detalles
    _delete_from_json(report_id)

    flash(f'Reporte #{report_id} eliminado', 'success')
    return redirect(url_for('panel.production_view', date=date))


def _delete_from_json(report_id: int):
    """Elimina un reporte del production_details.json."""
    import json as _json
    path = 'data/production_details.json'
    try:
        with open(path, encoding='utf-8') as f:
            records = _json.load(f)
        records = [r for r in records if str(r.get('id_reporte')) != str(report_id)]
        with open(path, 'w', encoding='utf-8') as f:
            _json.dump(records, f, ensure_ascii=False, indent=2)
    except (FileNotFoundError, _json.JSONDecodeError):
        pass


# ── Descargas CSV (generadas dinámicamente desde la DB) ────────────────────────

@admin_bp.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@admin_bp.route('/reportes/download/<report_type>')
@login_required
def download_report_csv(report_type):
    if report_type not in ('production', 'personal', 'company'):
        flash('Tipo de reporte inválido', 'error')
        return redirect(url_for('reportes'))

    if report_type == 'production':
        content  = export_production_csv()
        filename = 'production_reports.csv'
    elif report_type == 'personal':
        content  = export_simple_csv('personal_reports')
        filename = 'personal_reports.csv'
    else:
        content  = export_simple_csv('company_reports')
        filename = 'company_reports.csv'

    if not content.strip():
        flash('No hay reportes disponibles para descargar', 'error')
        return redirect(url_for('reportes'))

    return Response(
        content.encode('utf-8'),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


# ── Helpers privados ───────────────────────────────────────────────────────────

def _db_row_to_csv_dict(r: dict) -> dict:
    """Convierte una fila de la DB al formato de dict que espera el template."""
    return {
        'ID Reporte':               r['id'],
        'Nombre':                   r['nombre'],
        'Turno':                    r['turno'],
        'Fecha':                    r['fecha'],
        'Trabajadores':             r['trabajadores'],
        'Maquina 1 Cantidad':       r['maquina1_cantidad'],
        'Maquina 1 Tipo de Cepillo': r['maquina1_tipo'],
        'Maquina 1 Color':          r['maquina1_color'],
        'Maquina 2 Cantidad':       r['maquina2_cantidad'],
        'Maquina 2 Tipo de Cepillo': r['maquina2_tipo'],
        'Maquina 2 Color':          r['maquina2_color'],
        'Maquina 3 Cantidad':       r['maquina3_cantidad'],
        'Maquina 3 Tipo de Cepillo': r['maquina3_tipo'],
        'Maquina 3 Color':          r['maquina3_color'],
        'Ensamble':                 r['ensamble'],
        'Ensartado':                r['ensartado'],
        'Pegado':                   r['pegado'],
        'Entregas':                 r['entregas'],
        'Produccion Personal':      r['produccion_personal'],
        'Produccion Maquinas':      r['produccion_maquinas'],
        'Produccion Total':         r['produccion_total'],
        'Produccion por Persona por Hora': r['produccion_por_persona_hora'],
        'Notas Adicionales':        r['notas'],
        'Fecha y Hora de Envio':    r['timestamp'],
    }
