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
                      delete_production_report, parse_maquinas,
                      format_maquinas_text,
                      get_config_options, add_config_option)
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
    from blueprints.reports.production_sections import PRODUCTION_SECTIONS
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
        available_dates=available_dates,
        production_sections=PRODUCTION_SECTIONS,
        get_text=get_text)


@admin_bp.route('/reportes/stats')
@login_required
def production_stats():
    from blueprints.reports.production_sections import PRODUCTION_SECTIONS
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
        for m in parse_maquinas(r):
            qty   = _int(m.get('cantidad', 0))
            btype = (m.get('tipo') or '').strip()
            color = (m.get('color') or '').strip()
            if qty > 0:
                if btype:
                    brush_type_totals[btype] += qty
                if color:
                    brush_color_totals[color] += qty

    brush_types  = sorted(brush_type_totals.items(),  key=lambda x: x[1], reverse=True)
    brush_colors = sorted(brush_color_totals.items(), key=lambda x: x[1], reverse=True)

    # ── Estadísticas por sección (uds/persona/hora) ───────────────────────────
    section_stats = []
    for s in PRODUCTION_SECTIONS:
        col   = s['total_col']
        total = sum(_int(r.get(col, 0)) for r in reports)

        # Promedio histórico
        effics = []
        for r in reports:
            sec_total = _int(r.get(col, 0))
            workers   = _int(r.get('trabajadores', 0))
            turno     = r.get('turno', '')
            hours     = _shift_hours_for_shift(turno)
            if sec_total > 0 and workers > 0:
                effics.append(round(sec_total / (workers * hours), 2))
        avg_effic = round(sum(effics) / len(effics), 2) if effics else 0

        # Datos para gráfica: por fecha, una línea por turno
        # { fecha: { turno: uds/persona/hora } }
        by_date_turno: dict = {}
        for r in reports:
            sec_total = _int(r.get(col, 0))
            workers   = _int(r.get('trabajadores', 0))
            fecha     = r.get('fecha', '')
            turno     = r.get('turno', 'Desconocido')
            hours     = _shift_hours_for_shift(turno)
            if not fecha or workers == 0:
                continue
            val = round(sec_total / (workers * hours), 2)
            by_date_turno.setdefault(fecha, {})[turno] = val

        chart_dates_s = sorted(by_date_turno.keys())[-30:]
        turnos_in_data = sorted({t for d in by_date_turno.values() for t in d})
        chart_series = {
            turno: [by_date_turno.get(d, {}).get(turno, None) for d in chart_dates_s]
            for turno in turnos_in_data
        }

        section_stats.append({
            'key':          s['key'],
            'label':        s['label'],
            'total':        total,
            'avg_effic':    avg_effic,
            'chart_dates':  chart_dates_s,
            'chart_series': chart_series,  # {turno: [val|None, ...]}
        })

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
        'section_stats':       section_stats,
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
        from blueprints.reports.production_sections import PRODUCTION_SECTIONS

        name             = request.form['name'].strip()
        job_shift        = request.form['job_shift'].strip()
        date             = request.form['date'].strip()
        quantity_persons = int(request.form['quantity_persons'].strip())
        additional_notes = request.form.get('additional_notes', '').strip()

        maquinas_raw = request.form.get('maquinas', '')
        machine_data = _json.loads(maquinas_raw) if maquinas_raw else []

        def _parse_json_field(field):
            raw = request.form.get(field, '')
            if not raw:
                return []
            try:
                return [[p['name'], p['quantity']] for p in _json.loads(raw)]
            except (_json.JSONDecodeError, KeyError):
                return []

        section_data = {
            s['key']: _parse_json_field(f'{s["css_prefix"]}_products')
            for s in PRODUCTION_SECTIONS
        }

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

        total_production = sum(_sum(section_data[s['key']]) for s in PRODUCTION_SECTIONS)
        total_machines = sum(int(m['cantidad']) for m in machine_data)

        from blueprints.reports.routes.production import _shift_hours
        hours = _shift_hours(job_shift)
        try:
            production_per_person_hour = round(total_production / (quantity_persons * hours), 2)
        except ZeroDivisionError:
            production_per_person_hour = 0

        maquinas_serialized = _json.dumps([
            {'maquina': m['maquina'], 'cantidad': int(m['cantidad']), 'tipo': _gt(m['tipo']), 'color': _gt(m['color'])}
            for m in machine_data
        ], ensure_ascii=False)

        def _first_for_machine(num):
            for m in machine_data:
                if m['maquina'] == num:
                    return (int(m['cantidad']), _gt(m['tipo']), _gt(m['color']))
            return (0, '', '')
        m1, m2, m3 = _first_for_machine(1), _first_for_machine(2), _first_for_machine(3)

        update_production_report(
            report_id,
            nombre=name,
            turno=_gt(job_shift),
            fecha=date,
            trabajadores=quantity_persons,
            maquina1_cantidad=m1[0], maquina1_tipo=m1[1], maquina1_color=m1[2],
            maquina2_cantidad=m2[0], maquina2_tipo=m2[1], maquina2_color=m2[2],
            maquina3_cantidad=m3[0], maquina3_tipo=m3[1], maquina3_color=m3[2],
            **{s['key']: _format_products(section_data[s['key']]) for s in PRODUCTION_SECTIONS},
            entregas=_format_deliveries(delivery_data),
            produccion_personal=total_production,
            produccion_maquinas=total_machines,
            produccion_total=total_production + total_machines,
            produccion_por_persona_hora=production_per_person_hour,
            notas=additional_notes,
            maquinas=maquinas_serialized,
        )

        save_production_details_json(
            report_id, name, job_shift, date, quantity_persons,
            report['timestamp'], section_data,
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

    try:
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
            content,
            mimetype='text/csv; charset=utf-8',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'text/csv; charset=utf-8',
            },
        )
    except Exception as e:
        flash(f'Error al generar el CSV: {str(e)}', 'error')
        return redirect(url_for('reportes'))


# ── Config options (brush types & colors) ───────────────────────────────────────

import re as _re


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = _re.sub(r'[^a-z0-9\s-]', '', text)
    text = _re.sub(r'[\s-]+', '_', text)
    return text.strip('_')


@admin_bp.route('/reportes/api/config/<option_type>')
def api_config_options(option_type: str):
    if option_type not in ('brush_type', 'color'):
        return {'error': 'tipo invalido'}, 400
    options = get_config_options(option_type)
    return [{'key': o['option_key'], 'label': o['option_label']} for o in options]


@admin_bp.route('/reportes/config')
@login_required
def config_options_page():
    brush_types = get_config_options('brush_type')
    colors = get_config_options('color')
    return render_template('reports/config_options.html',
                           brush_types=brush_types,
                           colors=colors,
                           get_text=get_text)


@admin_bp.route('/reportes/config/agregar', methods=['POST'])
@login_required
def config_option_add():
    admin_password = os.getenv('ADMIN_PASSWORD', '')
    provided = request.form.get('admin_password', '')
    if not admin_password or provided != admin_password:
        flash('Contraseña de administrador incorrecta', 'error')
        return redirect(url_for('panel.config_options_page'))

    option_type = request.form.get('tipo', '')
    label = request.form.get('label', '').strip()
    if not label:
        flash('La etiqueta es obligatoria', 'error')
        return redirect(url_for('panel.config_options_page'))
    if option_type not in ('brush_type', 'color'):
        flash('Tipo invalido', 'error')
        return redirect(url_for('panel.config_options_page'))

    key = _slugify(label)
    if not key:
        flash('No se pudo generar una clave a partir de la etiqueta', 'error')
        return redirect(url_for('panel.config_options_page'))

    existing = get_config_options(option_type)
    if any(o['option_key'] == key for o in existing):
        flash(f'Ya existe una opcion con la clave "{key}"', 'error')
        return redirect(url_for('panel.config_options_page'))

    sort_order = (existing[-1]['sort_order'] + 1) if existing else 1
    add_config_option(option_type, key, label, sort_order)
    flash(f'"{label}" agregado correctamente', 'success')
    return redirect(url_for('panel.config_options_page'))


# ── Helpers privados ───────────────────────────────────────────────────────────

def _db_row_to_csv_dict(r: dict) -> dict:
    """Convierte una fila de la DB al formato de dict que espera el template."""
    from blueprints.reports.production_sections import PRODUCTION_SECTIONS
    maquinas_list = parse_maquinas(r)
    base = {
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
        '_maquinas_parsed':         maquinas_list,
        'Detalle Maquinas':         format_maquinas_text(maquinas_list),
    }
    for s in PRODUCTION_SECTIONS:
        base[s['csv_label']] = r.get(s['key'], '')
    base.update({
        'Entregas':                 r['entregas'],
        'Produccion Personal':      r['produccion_personal'],
        'Produccion Maquinas':      r['produccion_maquinas'],
        'Produccion Total':         r['produccion_total'],
        'Produccion por Persona por Hora': r['produccion_por_persona_hora'],
        'Notas Adicionales':        r['notas'],
        'Fecha y Hora de Envio':    r['timestamp'],
    })
    return base
