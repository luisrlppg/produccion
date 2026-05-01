import csv
import json
import os

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
