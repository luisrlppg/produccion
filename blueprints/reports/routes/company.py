import os

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from datetime import datetime
from werkzeug.utils import secure_filename
import os

from auth import login_required
from notifications import NotificationManager
from utils import get_text, get_next_report_id, save_report, allowed_file, build_simple_message

company_bp = Blueprint('company', __name__)


@company_bp.route('/report/company')
@login_required
def report_form():
    return render_template('reports/report_form.html', report_type='company', get_text=get_text)


@company_bp.route('/submit_report/company', methods=['POST'])
@login_required
def submit_report():
    report_id           = get_next_report_id('company')
    timestamp           = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    item_name           = request.form['item_name']
    location            = request.form.get('location', '')
    failure_description = request.form['failure_description']
    additional_info     = request.form.get('additional_info', '')
    photo_path          = ''

    if 'photo' in request.files:
        file = request.files['photo']
        if file and file.filename and allowed_file(file.filename):
            filename   = f'report_{report_id}_{secure_filename(file.filename)}'
            photo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
            file.save(photo_path)

    report_data = [report_id, 'company', item_name, location,
                   failure_description, additional_info, photo_path, timestamp]
    save_report(report_data, 'company')

    try:
        nm  = NotificationManager()
        base_url = os.getenv('APP_BASE_URL', '').rstrip('/')
        report_url = f'{base_url}/panel/company' if base_url else None
        msg = build_simple_message(report_id, 'company', item_name, failure_description, timestamp,
                                   report_url=report_url)
        nm.broadcast(
            subject=f'Nuevo Reporte Empresa #{report_id}',
            text=msg,
            report_type='company',
        )
    except Exception as e:
        print(f'[Company] Error enviando notificaciones: {e}')

    flash(get_text('success_msg').format(report_id), 'success')
    return redirect(url_for('index'))
