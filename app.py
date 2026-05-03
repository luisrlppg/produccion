"""
PPG Unified — aplicación Flask unificada.

Autenticación por sección:
  /reportes  → REPORTS_USERNAME / REPORTS_PASSWORD
  /signage/  → SIGNAGE_USERNAME / SIGNAGE_PASSWORD
  /          → público
"""
import os
import secrets

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for

from auth import (check_reports_credentials, check_signage_credentials,
                  reports_login_required)
from blueprints.signage import signage_bp
from blueprints.reports import personal_bp, company_bp, production_bp, admin_bp
from blueprints.labels import labels_bp
from database import init_db
from utils import get_text

load_dotenv()


def create_app() -> Flask:
    app = Flask(__name__, template_folder='templates', static_folder='static')

    secret_key = os.getenv('SECRET_KEY') or secrets.token_hex(32)
    if not os.getenv('SECRET_KEY'):
        print('WARNING: SECRET_KEY no encontrada en .env — usando clave generada.')

    app.config.update(
        SECRET_KEY         = secret_key,
        UPLOAD_FOLDER      = 'uploads',
        MAX_CONTENT_LENGTH = 16 * 1024 * 1024,
    )

    os.makedirs('uploads', exist_ok=True)
    os.makedirs('data',    exist_ok=True)
    init_db(app)

    app.jinja_env.filters['format_number'] = lambda v: '{:,}'.format(int(float(v)))

    # ── Página principal — pública ─────────────────────────────────────────────

    @app.route('/')
    def index():
        return render_template('index.html', get_text=get_text)

    # ── Login / logout de Reportes ─────────────────────────────────────────────

    @app.route('/login/reportes', methods=['GET', 'POST'])
    def login_reports():
        error = None
        if request.method == 'POST':
            if check_reports_credentials(
                request.form.get('username', ''),
                request.form.get('password', ''),
            ):
                session['reports_logged_in'] = True
                return redirect(request.args.get('next') or url_for('reportes'))
            error = 'Usuario o contraseña incorrectos'
        return render_template('login.html', error=error,
                               section='Reportes', get_text=get_text)

    @app.route('/logout/reportes')
    def logout_reports():
        session.pop('reports_logged_in', None)
        return redirect(url_for('index'))

    # ── Login / logout de Fabricación ──────────────────────────────────────────

    @app.route('/login/fabricacion', methods=['GET', 'POST'])
    def login_signage():
        error = None
        if request.method == 'POST':
            if check_signage_credentials(
                request.form.get('username', ''),
                request.form.get('password', ''),
            ):
                session['signage_logged_in'] = True
                return redirect(request.args.get('next') or url_for('signage.index'))
            error = 'Usuario o contraseña incorrectos'
        return render_template('login.html', error=error,
                               section='Fabricación y Stock', get_text=get_text)

    @app.route('/logout/fabricacion')
    def logout_signage():
        session.pop('signage_logged_in', None)
        return redirect(url_for('index'))

    # ── Rutas de Reportes ──────────────────────────────────────────────────────

    @app.route('/reportes')
    @reports_login_required
    def reportes():
        return render_template('reportes.html', get_text=get_text)

    @app.route('/report/<report_type>')
    @reports_login_required
    def report_form(report_type):
        if report_type not in ('personal', 'company', 'production'):
            return redirect(url_for('reportes'))
        return render_template('reports/report_form.html',
                               report_type=report_type, get_text=get_text)

    @app.route('/submit_report', methods=['POST'])
    @reports_login_required
    def submit_report():
        report_type = request.form.get('report_type')
        if report_type == 'production':
            from blueprints.reports.routes.production import submit_report as _fn
            return _fn()
        if report_type == 'personal':
            from blueprints.reports.routes.personal import submit_report as _fn
            return _fn()
        if report_type == 'company':
            from blueprints.reports.routes.company import submit_report as _fn
            return _fn()
        return redirect(url_for('reportes'))

    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'service': 'ppg-unified'}, 200

    # ── Blueprints ─────────────────────────────────────────────────────────────
    app.register_blueprint(signage_bp)
    app.register_blueprint(personal_bp)
    app.register_blueprint(company_bp)
    app.register_blueprint(production_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(labels_bp)

    return app


app = create_app()

if __name__ == '__main__':
    port  = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)
