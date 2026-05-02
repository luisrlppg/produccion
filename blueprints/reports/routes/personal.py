import os

from flask import Blueprint, render_template, request, redirect, url_for, flash
from datetime import datetime

from auth import login_required
from notifications import NotificationManager
from utils import get_text, get_next_report_id, save_report, build_simple_message

personal_bp = Blueprint('personal', __name__)


@personal_bp.route('/report/personal')
@login_required
def report_form():
    return render_template('reports/report_form.html', report_type='personal', get_text=get_text)


@personal_bp.route('/submit_report/personal', methods=['POST'])
@login_required
def submit_report():
    report_id           = get_next_report_id('personal')
    timestamp           = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    item_name           = request.form['item_name']
    failure_description = request.form['failure_description']
    location            = request.form.get('location', '')
    additional_info     = request.form.get('additional_info', '')

    report_data = [report_id, 'personal', item_name, location,
                   failure_description, additional_info, '', timestamp]
    save_report(report_data, 'personal')

    try:
        nm  = NotificationManager()
        base_url = os.getenv('APP_BASE_URL', '').rstrip('/')
        report_url = f'{base_url}/panel/personal' if base_url else None
        msg = build_simple_message(report_id, 'personal', item_name, failure_description, timestamp,
                                   report_url=report_url)
        nm.broadcast(
            subject=f'Nuevo Reporte Personal #{report_id}',
            text=msg,
            report_type='personal',
        )
    except Exception as e:
        print(f'[Personal] Error enviando notificaciones: {e}')

    flash(get_text('success_msg').format(report_id), 'success')
    return redirect(url_for('index'))
