import io
import json
import os
from collections import defaultdict

from flask import (Blueprint, Response, current_app, flash, redirect,
                   render_template, request, send_from_directory, url_for)

from auth import login_required
from database import (get_production_reports, get_production_dates,
                      get_all_production_reports, get_simple_reports,
                      export_production_csv, export_simple_csv)
from utils import get_text, read_production_details_json

admin_bp = Blueprint('panel', __name__)


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

    efficiencies = [_float(r['produccion_por_trabajador']) for r in reports
                    if _float(r['produccion_por_trabajador']) > 0]
    avg_efficiency  = round(sum(efficiencies) / len(efficiencies), 1) if efficiencies else 0
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
        round(by_date[d]['total'] / by_date[d]['workers'], 1)
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
                'name':           s,
                'total':          d['total'],
                'machines':       d['machines'],
                'reports':        d['reports'],
                'avg_per_worker': round(d['total'] / d['workers'], 1) if d['workers'] else 0,
            })
    for s, d in by_shift.items():
        if s not in shift_order:
            shifts_data.append({
                'name':           s,
                'total':          d['total'],
                'machines':       d['machines'],
                'reports':        d['reports'],
                'avg_per_worker': round(d['total'] / d['workers'], 1) if d['workers'] else 0,
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
        'Produccion por Trabajador': r['produccion_por_trabajador'],
        'Notas Adicionales':        r['notas'],
        'Fecha y Hora de Envio':    r['timestamp'],
    }
