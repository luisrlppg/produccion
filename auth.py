"""
Autenticación unificada — PPG Unified

Una sola sesión para toda la app:
  session['logged_in'] → acceso a todas las rutas protegidas

Credenciales en .env:
  APP_USERNAME / APP_PASSWORD
"""
import os
from functools import wraps
from flask import session, redirect, url_for, request, jsonify


# ── Decorador único ────────────────────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'No autenticado'}), 401
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated


# Aliases para compatibilidad con blueprints que usan nombres específicos
reports_login_required  = login_required
signage_login_required  = login_required


# ── Verificación de credenciales ───────────────────────────────────────────────

def check_credentials(username: str, password: str) -> bool:
    return (username.strip() == os.getenv('APP_USERNAME', 'admin')
            and password == os.getenv('APP_PASSWORD', 'ppg1234'))


# Aliases para compatibilidad con código existente
def check_reports_credentials(username: str, password: str) -> bool:
    return check_credentials(username, password)


def check_signage_credentials(username: str, password: str) -> bool:
    return check_credentials(username, password)
