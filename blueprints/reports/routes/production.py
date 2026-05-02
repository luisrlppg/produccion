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
                   build_production_email_body)

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
    timestamp        = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
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
        total_machines = sum(int(m[1]) for m in machine_data)
    except (ValueError, IndexError):
        total_machines = 0
    try:
        production_per_worker = round(total_production / quantity_persons, 2)
    except ZeroDivisionError:
        production_per_worker = 0

    # Máquinas como campos individuales
    machines = {str(m[0]): m for m in machine_data}
    def mf(num):
        m = machines.get(str(num))
        return (int(m[1]), get_text(m[2]), get_text(m[3])) if m else (0, '', '')

    m1, m2, m3 = mf(1), mf(2), mf(3)

    # ── Guardar en SQLite ──────────────────────────────────────────────────────
    report_id = insert_production_report(
        nombre=name,
        turno=get_text(job_shift),
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
        produccion_por_trabajador=production_per_worker,
        notas=additional_notes,
        timestamp=timestamp,
    )

    # ── Guardar detalle en JSON (se mantiene) ──────────────────────────────────
    save_production_details_json(
        report_id, name, job_shift, date, quantity_persons,
        timestamp, assembly_data, stringing_data, gluing_data,
    )

    # ── Notificaciones ─────────────────────────────────────────────────────────
    try:
        nm       = NotificationManager()
        base_url = os.getenv('APP_BASE_URL', '').rstrip('/')
        report_url = f'{base_url}/reportes/vista?date={date}' if base_url else None

        simple_msg = f'📋 Nuevo reporte de producción #{report_id} — {name} ({get_text(job_shift)})'
        if report_url:
            simple_msg += f'\n🔗 {report_url}'

        telegram_msg = simple_msg
        email_body = build_production_email_body(
            report_id, name, job_shift, date, quantity_persons,
            machine_data, assembly_data, stringing_data, gluing_data, delivery_data,
            total_production, total_machines, production_per_worker, additional_notes, timestamp,
        )
        nm.broadcast(
            subject=f'Nuevo Reporte de Produccion #{report_id} - {name}',
            text=email_body,
            telegram_text=simple_msg,
            whatsapp_text=simple_msg,
            report_type='production',
        )
    except Exception as e:
        print(f'[Production] Error enviando notificaciones: {e}')

    flash(get_text('success_msg').format(report_id), 'success')
    return redirect(url_for('reportes'))
