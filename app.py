"""
PPG Unified — aplicación Flask unificada.

Autenticación única para toda la app:
  APP_USERNAME / APP_PASSWORD  en .env
"""
import os
import secrets

from dotenv import load_dotenv
from flask import Flask, redirect, render_template, request, session, url_for

from auth import check_credentials, login_required
from blueprints.signage import signage_bp
from blueprints.reports import personal_bp, company_bp, production_bp, admin_bp
from blueprints.labels import labels_bp
from database import init_db
from utils import get_text

load_dotenv()


def _start_stock_scheduler():
    """Inicia el job de verificación de stock cada 8 horas."""
    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from blueprints.signage.stock_monitor import StockMonitor

        monitor   = StockMonitor()
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            func             = lambda: monitor.check_and_notify(force=False),
            trigger          = 'interval',
            hours            = 8,
            id               = 'stock_check',
            name             = 'Verificación de stock bajo',
            replace_existing = True,
        )
        scheduler.start()
        print('[Scheduler] Verificación de stock cada 8 horas iniciada.')
    except Exception as e:
        print(f'[Scheduler] Error al iniciar: {e}')


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

    # ── Login / logout ─────────────────────────────────────────────────────────

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if session.get('logged_in'):
            return redirect(url_for('index'))
        error = None
        if request.method == 'POST':
            if check_credentials(
                request.form.get('username', ''),
                request.form.get('password', ''),
            ):
                session['logged_in'] = True
                return redirect(request.args.get('next') or url_for('index'))
            error = 'Usuario o contraseña incorrectos'
        return render_template('login.html', error=error,
                               section='PPG', get_text=get_text)

    @app.route('/logout')
    def logout():
        session.clear()
        return redirect(url_for('login'))

    # Rutas legacy de login para compatibilidad con links guardados
    @app.route('/login/reportes')
    @app.route('/login/fabricacion')
    def login_legacy():
        return redirect(url_for('login', **request.args))

    @app.route('/logout/reportes')
    @app.route('/logout/fabricacion')
    def logout_legacy():
        session.clear()
        return redirect(url_for('login'))

    # ── Rutas principales ──────────────────────────────────────────────────────

    @app.route('/')
    @login_required
    def index():
        return render_template('index.html', get_text=get_text)

    @app.route('/reportes')
    @login_required
    def reportes():
        return render_template('reportes.html', get_text=get_text)

    @app.route('/report/<report_type>')
    @login_required
    def report_form(report_type):
        if report_type not in ('personal', 'company', 'production'):
            return redirect(url_for('reportes'))
        return render_template('reports/report_form.html',
                               report_type=report_type, get_text=get_text)

    @app.route('/submit_report', methods=['POST'])
    @login_required
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

    # Iniciar scheduler solo una vez (no en el reloader de desarrollo)
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        _start_stock_scheduler()

    return app


app = create_app()

if __name__ == '__main__':
    port  = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_ENV') != 'production'
    app.run(host='0.0.0.0', port=port, debug=debug)
