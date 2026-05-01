"""
Autenticación por sección — PPG Unified

Dos sesiones independientes:
  session['reports_logged_in']  → acceso a /reportes y rutas de reportes
  session['signage_logged_in']  → acceso a /signage/ y rutas de fabricación

Credenciales en .env:
  REPORTS_USERNAME / REPORTS_PASSWORD
  SIGNAGE_USERNAME / SIGNAGE_PASSWORD
"""
import os
from functools import wraps
from flask import session, redirect, url_for, request, jsonify


# ── Decoradores ────────────────────────────────────────────────────────────────

def reports_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('reports_logged_in'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'No autenticado'}), 401
            return redirect(url_for('login_reports', next=request.path))
        return f(*args, **kwargs)
    return decorated


def signage_login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('signage_logged_in'):
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'error': 'No autenticado'}), 401
            return redirect(url_for('login_signage', next=request.path))
        return f(*args, **kwargs)
    return decorated


# Alias para compatibilidad con blueprints que importan login_required genérico
login_required = reports_login_required


# ── Verificación de credenciales ───────────────────────────────────────────────

def check_reports_credentials(username: str, password: str) -> bool:
    return (username.strip() == os.getenv('REPORTS_USERNAME', 'admin')
            and password == os.getenv('REPORTS_PASSWORD', 'ppg1234'))


def check_signage_credentials(username: str, password: str) -> bool:
    return (username.strip() == os.getenv('SIGNAGE_USERNAME', 'admin')
            and password == os.getenv('SIGNAGE_PASSWORD', 'ppg1234'))
