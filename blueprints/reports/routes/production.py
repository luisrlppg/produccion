# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime
import json
import os

from auth import login_required
from notifications import NotificationManager
from utils import (get_text, get_next_report_id, save_production_report,
                   build_production_message, build_production_email_body)

production_bp = Blueprint('production', __name__)


@production_bp.route('/report/production')
@login_required
def report_form():
    return render_template('reports/report_form.html', report_type='production', get_text=get_text)


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
    report_id        = get_next_report_id('production')
    timestamp        = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    name             = request.form['name'].strip()
    job_shift        = request.form['job_shift'].strip()
    date             = request.form['date'].strip()
    quantity_persons = request.form['quantity_persons'].strip()
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
            return [[p['name'], p['quantity']] for p in json.loads(raw)]
        except (json.JSONDecodeError, KeyError):
            return []

    assembly_data  = _parse_json_field('assembly_products')
    stringing_data = _parse_json_field('stringing_products')
    gluing_data    = _parse_json_field('gluing_products')

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

    total_production = _sum(assembly_data) + _sum(stringing_data) + _sum(gluing_data)
    try:
        production_per_worker = round(total_production / int(quantity_persons), 2)
    except (ValueError, ZeroDivisionError):
        production_per_worker = 0

    # ── Guardar ────────────────────────────────────────────────────────────────
    save_production_report(
        report_id, name, job_shift, date, quantity_persons, additional_notes, timestamp,
        machine_data, assembly_data, stringing_data, gluing_data, delivery_data,
        total_production, production_per_worker,
    )

    # ── Notificaciones ─────────────────────────────────────────────────────────
    try:
        nm  = NotificationManager()
        base_url = os.getenv('APP_BASE_URL', '').rstrip('/')
        report_url = f'{base_url}/panel/production/view?date={date}' if base_url else None
        msg = build_production_message(
            report_id, name, job_shift, date, quantity_persons,
            machine_data, assembly_data, stringing_data, gluing_data, delivery_data,
            total_production, production_per_worker, additional_notes, timestamp,
            report_url=report_url,
        )
        email_body = build_production_email_body(
            report_id, name, job_shift, date, quantity_persons,
            machine_data, assembly_data, stringing_data, gluing_data, delivery_data,
            total_production, production_per_worker, additional_notes, timestamp,
        )
        nm.broadcast(
            subject=f'Nuevo Reporte de Produccion #{report_id} - {name}',
            text=email_body,
            telegram_text=msg,
            report_type='production',
        )
    except Exception as e:
        print(f'[Production] Error enviando notificaciones: {e}')

    flash(get_text('success_msg').format(report_id), 'success')
    return redirect(url_for('reportes'))
