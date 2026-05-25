# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
import json
import os

from auth import login_required
from notifications import NotificationManager
from database import insert_production_report
from utils import (get_text, _format_products, _format_deliveries,
                   save_production_details_json,
                   build_production_email_body_from_db)
from blueprints.reports.production_sections import PRODUCTION_SECTIONS

# Horas por turno
SHIFT_HOURS = {
    'morning':   8.0,
    'afternoon': 7.5,
    'night':     8.0,
}

production_bp = Blueprint('production', __name__)


def _shift_hours(job_shift: str) -> float:
    return SHIFT_HOURS.get(job_shift, 8.0)


@production_bp.route('/report/production')
@login_required
def report_form():
    return render_template('reports/report_form.html',
                           report_type='production',
                           production_sections=PRODUCTION_SECTIONS,
                           get_text=get_text)


@production_bp.route('/submit_report/production', methods=['POST'])
@login_required
def submit_report():
    # ── Validación ─────────────────────────────────────────────────────────────
    required = {'name': 'Nombre', 'job_shift': 'Turno de Trabajo',
                'date': 'Fecha', 'quantity_persons': 'Cantidad de Personas'}
    errors = [f"El campo '{label}' es obligatorio"
              for field, label in required.items()
              if not request.form.get(field, '').strip()]

    qty_raw = request.form.get('quantity_persons', '').strip()
    if qty_raw:
        try:
            if int(qty_raw) <= 0:
                errors.append('La cantidad de personas debe ser mayor a 0')
        except ValueError:
            errors.append('La cantidad de personas debe ser un número válido')

    if errors:
        for e in errors:
            flash(e, 'error')
        return redirect(url_for('report_form', report_type='production'))

    # ── Datos del formulario ───────────────────────────────────────────────────
    timestamp        = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    name             = request.form['name'].strip()
    job_shift        = request.form['job_shift'].strip()
    date             = request.form['date'].strip()
    quantity_persons = int(request.form['quantity_persons'].strip())
    additional_notes = request.form.get('additional_notes', '').strip()

    # Máquinas (JSON: [{"maquina":1, "cantidad":100, "tipo":"straight", "color":"black"}, ...])
    maquinas_raw = request.form.get('maquinas', '')
    machine_data = json.loads(maquinas_raw) if maquinas_raw else []

    def _parse_json_field(field):
        raw = request.form.get(field, '')
        if not raw:
            return []
        try:
            return [[p['name'], p['quantity']] for p in json.loads(raw)]
        except (json.JSONDecodeError, KeyError):
            return []

    # Parsear todas las secciones dinámicamente
    section_data = {
        s['key']: _parse_json_field(f'{s["css_prefix"]}_products')
        for s in PRODUCTION_SECTIONS
    }

    delivery_data = []
    raw = request.form.get('deliveries', '')
    if raw:
        try:
            delivery_data = [[d['customer'], d['description'], d.get('quantity', 1)]
                             for d in json.loads(raw)]
        except (json.JSONDecodeError, KeyError):
            pass

    # Totales
    def _sum(data):
        total = 0
        for row in data:
            try:
                total += int(row[1])
            except (ValueError, IndexError):
                pass
        return total

    total_production = sum(_sum(section_data[s['key']]) for s in PRODUCTION_SECTIONS)
    # Totales individuales por sección para estadísticas
    section_totals = {s['key']: _sum(section_data[s['key']]) for s in PRODUCTION_SECTIONS}
    total_machines = sum(int(m['cantidad']) for m in machine_data)

    hours = _shift_hours(job_shift)
    try:
        production_per_person_hour = round(total_production / (quantity_persons * hours), 2)
    except ZeroDivisionError:
        production_per_person_hour = 0

    # Preparar JSON de máquinas (traducir tipo/color a labels)
    maquinas_serialized = json.dumps([
        {
            'maquina': m['maquina'],
            'cantidad': int(m['cantidad']),
            'tipo': get_text(m['tipo']),
            'color': get_text(m['color']),
        }
        for m in machine_data
    ], ensure_ascii=False)

    # Columnas viejas: primer valor de cada máquina o 0
    def _first_for_machine(num):
        for m in machine_data:
            if m['maquina'] == num:
                return (int(m['cantidad']), get_text(m['tipo']), get_text(m['color']))
        return (0, '', '')
    m1, m2, m3 = _first_for_machine(1), _first_for_machine(2), _first_for_machine(3)

    # ── Guardar en SQLite ──────────────────────────────────────────────────────
    report_id = insert_production_report(
        nombre=name,
        turno=get_text(job_shift),
        fecha=date,
        trabajadores=quantity_persons,
        maquina1_cantidad=m1[0], maquina1_tipo=m1[1], maquina1_color=m1[2],
        maquina2_cantidad=m2[0], maquina2_tipo=m2[1], maquina2_color=m2[2],
        maquina3_cantidad=m3[0], maquina3_tipo=m3[1], maquina3_color=m3[2],
        section_data={s['key']: _format_products(section_data[s['key']]) for s in PRODUCTION_SECTIONS},
        section_totals=section_totals,
        entregas=_format_deliveries(delivery_data),
        produccion_personal=total_production,
        produccion_maquinas=total_machines,
        produccion_total=total_production + total_machines,
        produccion_por_persona_hora=production_per_person_hour,
        notas=additional_notes,
        timestamp=timestamp,
        maquinas=maquinas_serialized,
    )

    # ── Guardar detalle en JSON ────────────────────────────────────────────────
    save_production_details_json(
        report_id, name, job_shift, date, quantity_persons,
        timestamp, section_data,
    )

    # ── Notificaciones — leer de DB, no de memoria ─────────────────────────────
    try:
        from database import get_production_report_by_id
        nm         = NotificationManager()
        base_url   = os.getenv('APP_BASE_URL', '').rstrip('/')
        report_url = f'{base_url}/reportes/vista?date={date}' if base_url else None

        saved      = get_production_report_by_id(report_id)
        simple_msg = f'📋 Nuevo reporte de producción #{report_id} — {name} ({get_text(job_shift)})'
        if report_url:
            simple_msg += f'\n🔗 {report_url}'

        email_html = build_production_email_body_from_db(saved, report_url=report_url)

        nm.broadcast(
            subject=f'Nuevo Reporte de Produccion #{report_id} - {name}',
            text=f'Nuevo reporte de producción #{report_id} — {name} ({get_text(job_shift)}) — {date}',
            html=email_html,
            telegram_text=simple_msg,
            whatsapp_text=simple_msg,
            report_type='production',
        )
    except Exception as e:
        print(f'[Production] Error enviando notificaciones: {e}')

    flash(get_text('success_msg').format(report_id), 'success')
    return redirect(url_for('reportes'))
