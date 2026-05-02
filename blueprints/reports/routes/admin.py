import csv
import json
import os
from collections import defaultdict

from flask import (Blueprint, current_app, flash, redirect, render_template,
                   request, send_file, send_from_directory, url_for)

from auth import login_required
from utils import get_text

admin_bp = Blueprint('admin', __name__)


# ── Vistas ─────────────────────────────────────────────────────────────────────

@admin_bp.route('/admin')
@login_required
def admin_dashboard():
    return render_template('reports/admin_dashboard.html', get_text=get_text)


@admin_bp.route('/admin/production')
@login_required
def admin_production():
    return render_template('reports/admin_production.html', get_text=get_text)


@admin_bp.route('/admin/production/stats')
@login_required
def production_stats():
    csv_reports  = _read_csv('data/production_reports.csv')
    json_reports = _read_json('data/production_details.json')

    if not csv_reports:
        return render_template('reports/admin_production_stats.html',
                               stats=None, get_text=get_text)

    # ── Helpers ────────────────────────────────────────────────────────────────
    def _int(val, default=0):
        try:
            return int(val)
        except (ValueError, TypeError):
            return default

    def _float(val, default=0.0):
        try:
            return float(val)
        except (ValueError, TypeError):
            return default

    # ── Totales globales ───────────────────────────────────────────────────────
    total_reports     = len(csv_reports)
    total_production  = sum(_int(r.get('Produccion Total', 0)) for r in csv_reports)
    total_workers_sum = sum(_int(r.get('Trabajadores', 0)) for r in csv_reports)
    avg_workers       = round(total_workers_sum / total_reports, 1) if total_reports else 0

    efficiencies = [_float(r.get('Produccion por Trabajador', 0)) for r in csv_reports
                    if _float(r.get('Produccion por Trabajador', 0)) > 0]
    avg_efficiency = round(sum(efficiencies) / len(efficiencies), 1) if efficiencies else 0
    best_efficiency = max(efficiencies) if efficiencies else 0

    # ── Producción por fecha (ordenada) ───────────────────────────────────────
    by_date = defaultdict(lambda: {'total': 0, 'workers': 0, 'reports': 0})
    for r in csv_reports:
        d = r.get('Fecha', '')
        if not d:
            continue
        by_date[d]['total']   += _int(r.get('Produccion Total', 0))
        by_date[d]['workers'] += _int(r.get('Trabajadores', 0))
        by_date[d]['reports'] += 1

    dates_sorted = sorted(by_date.keys())
    chart_dates        = dates_sorted[-30:]   # últimas 30 fechas
    chart_production   = [by_date[d]['total']   for d in chart_dates]
    chart_workers      = [by_date[d]['workers'] for d in chart_dates]
    chart_efficiency   = [
        round(by_date[d]['total'] / by_date[d]['workers'], 1)
        if by_date[d]['workers'] else 0
        for d in chart_dates
    ]

    # ── Por turno ─────────────────────────────────────────────────────────────
    by_shift = defaultdict(lambda: {'total': 0, 'reports': 0, 'workers': 0})
    for r in csv_reports:
        shift = r.get('Turno', 'Desconocido')
        by_shift[shift]['total']   += _int(r.get('Produccion Total', 0))
        by_shift[shift]['reports'] += 1
        by_shift[shift]['workers'] += _int(r.get('Trabajadores', 0))

    shift_order = ['Matutino', 'Vespertino', 'Nocturno']
    shifts_data = []
    for s in shift_order:
        if s in by_shift:
            d = by_shift[s]
            shifts_data.append({
                'name':       s,
                'total':      d['total'],
                'reports':    d['reports'],
                'avg_per_worker': round(d['total'] / d['workers'], 1) if d['workers'] else 0,
            })
    # Añadir turnos no estándar si los hay
    for s, d in by_shift.items():
        if s not in shift_order:
            shifts_data.append({
                'name':       s,
                'total':      d['total'],
                'reports':    d['reports'],
                'avg_per_worker': round(d['total'] / d['workers'], 1) if d['workers'] else 0,
            })

    # ── Top productos (desde JSON) ─────────────────────────────────────────────
    product_totals = defaultdict(lambda: {'ensamble': 0, 'ensartado': 0, 'pegado': 0, 'total': 0})
    for jr in json_reports:
        for op in ('ensamble', 'ensartado', 'pegado'):
            for item in jr.get(op, []):
                name = item.get('producto', '').strip()
                qty  = _int(item.get('cantidad', 0))
                if name and qty > 0:
                    product_totals[name][op]    += qty
                    product_totals[name]['total'] += qty

    top_products = sorted(product_totals.items(), key=lambda x: x[1]['total'], reverse=True)[:10]

    # ── Máquinas: tipo de cepillo y color ─────────────────────────────────────
    brush_type_totals = defaultdict(int)
    brush_color_totals = defaultdict(int)
    for r in csv_reports:
        for i in range(1, 4):
            qty   = _int(r.get(f'Maquina {i} Cantidad', 0))
            btype = r.get(f'Maquina {i} Tipo de Cepillo', '').strip()
            color = r.get(f'Maquina {i} Color', '').strip()
            # Compatibilidad con columna "Tipo de Brocha"
            if not btype:
                btype = r.get(f'Maquina {i} Tipo de Brocha', '').strip()
            if qty > 0:
                if btype:
                    brush_type_totals[btype] += qty
                if color:
                    brush_color_totals[color] += qty

    brush_types  = sorted(brush_type_totals.items(),  key=lambda x: x[1], reverse=True)
    brush_colors = sorted(brush_color_totals.items(), key=lambda x: x[1], reverse=True)

    # ── Mejor y peor día ──────────────────────────────────────────────────────
    best_day  = max(by_date.items(), key=lambda x: x[1]['total']) if by_date else None
    worst_day = min(
        ((d, v) for d, v in by_date.items() if v['total'] > 0),
        key=lambda x: x[1]['total'],
        default=None,
    )

    # ── Reportes recientes ────────────────────────────────────────────────────
    recent = sorted(csv_reports, key=lambda x: x.get('Fecha y Hora de Envio', ''), reverse=True)[:5]

    stats = {
        # Globales
        'total_reports':    total_reports,
        'total_production': total_production,
        'avg_workers':      avg_workers,
        'avg_efficiency':   avg_efficiency,
        'best_efficiency':  best_efficiency,
        # Gráficas
        'chart_dates':      chart_dates,
        'chart_production': chart_production,
        'chart_workers':    chart_workers,
        'chart_efficiency': chart_efficiency,
        # Turnos
        'shifts_data':      shifts_data,
        # Productos
        'top_products':     top_products,
        # Máquinas
        'brush_types':      brush_types,
        'brush_colors':     brush_colors,
        # Días destacados
        'best_day':         best_day,
        'worst_day':        worst_day,
        # Recientes
        'recent':           recent,
    }

    return render_template('reports/admin_production_stats.html',
                           stats=stats, get_text=get_text)


@admin_bp.route('/admin/production/view')
@login_required
def production_view():
    selected_date  = request.args.get('date', '')
    csv_reports    = _read_csv('data/production_reports.csv')
    json_reports   = _read_json('data/production_details.json')
    available_dates = sorted(
        {r.get('Fecha', '') for r in csv_reports if r.get('Fecha')},
        reverse=True,
    )

    filtered = []
    if selected_date:
        for csv_r in csv_reports:
            if csv_r.get('Fecha') == selected_date:
                json_d = next(
                    (j for j in json_reports if str(j.get('id_reporte')) == str(csv_r.get('ID Reporte'))),
                    None,
                )
                filtered.append({'csv': csv_r, 'json': json_d})

    return render_template('reports/admin_production_view.html',
        reports=filtered, selected_date=selected_date,
        available_dates=available_dates, get_text=get_text)


@admin_bp.route('/admin/personal')
@login_required
def admin_personal():
    reports = sorted(_read_csv('data/personal_reports.csv'),
                     key=lambda x: int(x.get('Report_ID', 0)), reverse=True)
    return render_template('reports/admin_personal.html', reports=reports, get_text=get_text)


@admin_bp.route('/admin/company')
@login_required
def admin_company():
    reports = sorted(_read_csv('data/company_reports.csv'),
                     key=lambda x: int(x.get('Report_ID', 0)), reverse=True)
    return render_template('reports/admin_company.html', reports=reports, get_text=get_text)


@admin_bp.route('/admin/reports')
@login_required
def admin_reports():
    reports = sorted(_read_csv('data/reports.csv'),
                     key=lambda x: int(x.get('Report_ID', 0)), reverse=True)
    return render_template('reports/admin_reports.html', reports=reports, get_text=get_text)


# ── Archivos ───────────────────────────────────────────────────────────────────

@admin_bp.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)


@admin_bp.route('/admin/download')
@login_required
def download_csv():
    path = 'data/reports.csv'
    if os.path.exists(path):
        return send_file(path, as_attachment=True, download_name='reports.csv')
    flash('No hay reportes disponibles', 'error')
    return redirect(url_for('admin.admin_dashboard'))


@admin_bp.route('/admin/download/<report_type>')
@login_required
def download_report_csv(report_type):
    if report_type not in ('production', 'personal', 'company'):
        flash('Tipo de reporte invalido', 'error')
        return redirect(url_for('admin.admin_dashboard'))
    path = f'data/{report_type}_reports.csv'
    if os.path.exists(path):
        return send_file(path, as_attachment=True, download_name=f'{report_type}_reports.csv')
    flash(f'No hay reportes de {report_type} disponibles', 'error')
    return redirect(url_for('admin.admin_dashboard'))


# ── Helpers privados ───────────────────────────────────────────────────────────

def _read_csv(path: str) -> list:
    try:
        with open(path, encoding='utf-8') as f:
            return list(csv.DictReader(f))
    except FileNotFoundError:
        return []


def _read_json(path: str) -> list:
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
