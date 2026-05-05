"""
NotificationManager — punto único de envío de notificaciones.

Soporta:
  - Email (SMTP directo, sin Flask-Mail)
  - Telegram (Bot API via requests, sin python-telegram-bot)
  - WhatsApp CallMeBot (gratuito, personal)
  - WhatsApp Meta Business API (oficial, de pago)

Cada canal puede tener destinatarios globales o por tipo de reporte
(production, personal, company, stock).  Si existen los específicos
se usan en lugar de los globales.
"""

import os
import smtplib
import requests
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


# ── Helpers de entorno ─────────────────────────────────────────────────────────

def _csv_env(key: str) -> list[str]:
    """Lee una variable de entorno CSV y devuelve lista limpia."""
    return [v.strip() for v in os.getenv(key, '').split(',') if v.strip()]


def _parse_callmebot(raw: str) -> list[dict]:
    """Parsea 'numero:apikey,numero:apikey' → lista de dicts."""
    result = []
    for entry in raw.split(','):
        entry = entry.strip()
        if ':' in entry:
            phone, apikey = entry.split(':', 1)
            result.append({'phone': phone.strip(), 'apikey': apikey.strip()})
    return result


# ── Clase principal ────────────────────────────────────────────────────────────

class NotificationManager:
    """
    Gestiona el envío de notificaciones por múltiples canales.

    Parámetro `report_type` en los métodos send_*:
        'production' | 'personal' | 'company' | 'stock' | None
        Cuando se especifica, se buscan primero variables específicas del tipo
        (ej. TELEGRAM_PRODUCTION_RECIPIENTS) y si no existen se usan las globales
        (TELEGRAM_CHAT_IDS).
    """

    # ── Init ───────────────────────────────────────────────────────────────────

    def __init__(self):
        # Email
        self.smtp_server    = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port      = int(os.getenv('SMTP_PORT', '587'))
        self.email_user     = os.getenv('EMAIL_USER', '')
        self.email_password = os.getenv('EMAIL_PASSWORD', '')

        # Telegram
        self.telegram_token = os.getenv('TELEGRAM_BOT_TOKEN', '')

        # WhatsApp Meta (global, sin tipo)
        self.wa_meta_token      = os.getenv('WHATSAPP_TOKEN', '')
        self.wa_meta_phone_id   = os.getenv('WHATSAPP_PHONE_ID', '')
        self.wa_meta_recipients = _csv_env('WHATSAPP_RECIPIENTS')

    # ── Resolución de destinatarios ────────────────────────────────────────────

    def _email_recipients(self, report_type: str | None) -> list[str]:
        """Destinatarios de email para el tipo dado."""
        type_map = {
            'production': 'PRODUCTION_EMAIL_RECIPIENTS',
            'personal':   'PERSONAL_EMAIL_RECIPIENTS',
            'company':    'COMPANY_EMAIL_RECIPIENTS',
            'stock':      'EMAIL_RECIPIENTS',
        }
        if report_type and report_type in type_map:
            specific = _csv_env(type_map[report_type])
            if specific:
                return specific
        # Fallback global
        return _csv_env('EMAIL_RECIPIENTS')

    def _telegram_chat_ids(self, report_type: str | None) -> list[str]:
        """Chat IDs de Telegram para el tipo dado."""
        type_map = {
            'production': 'TELEGRAM_PRODUCTION_RECIPIENTS',
            'personal':   'TELEGRAM_PERSONAL_RECIPIENTS',
            'company':    'TELEGRAM_COMPANY_RECIPIENTS',
            'stock':      'TELEGRAM_CHAT_IDS',
        }
        if report_type and report_type in type_map:
            specific = _csv_env(type_map[report_type])
            if specific:
                return specific
        return _csv_env('TELEGRAM_CHAT_IDS')

    def _callmebot_numbers(self, report_type: str | None) -> list[dict]:
        """Números CallMeBot para el tipo dado."""
        type_map = {
            'production': 'WHATSAPP_PRODUCTION_RECIPIENTS',
            'personal':   'WHATSAPP_PERSONAL_RECIPIENTS',
            'company':    'WHATSAPP_COMPANY_RECIPIENTS',
            'stock':      'CALLMEBOT_NUMBERS',
        }
        if report_type and report_type in type_map:
            raw = os.getenv(type_map[report_type], '')
            if raw.strip():
                return _parse_callmebot(raw)
        return _parse_callmebot(os.getenv('CALLMEBOT_NUMBERS', ''))

    # ── Email ──────────────────────────────────────────────────────────────────

    def send_email(self, subject: str, body: str, html_body: str | None = None,
                   report_type: str | None = None) -> bool:
        """Envía email por SMTP. Retorna True si tuvo éxito."""
        recipients = self._email_recipients(report_type)
        if not self.email_user or not self.email_password or not recipients:
            print('[Email] No configurado — omitiendo')
            return False
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From']    = self.email_user
            msg['To']      = ', '.join(recipients)
            msg.attach(MIMEText(body, 'plain', 'utf-8'))
            if html_body:
                msg.attach(MIMEText(html_body, 'html', 'utf-8'))

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_user, self.email_password)
                server.send_message(msg)

            print(f'[Email] Enviado a {len(recipients)} destinatario(s)')
            return True
        except Exception as e:
            print(f'[Email] Error: {e}')
            return False

    # ── Telegram ───────────────────────────────────────────────────────────────

    def send_telegram(self, message: str, report_type: str | None = None) -> bool:
        """Envía mensaje de Telegram via Bot API (requests, sin dependencia extra)."""
        if not self.telegram_token:
            print('[Telegram] TELEGRAM_BOT_TOKEN no configurado — omitiendo')
            return False

        chat_ids = self._telegram_chat_ids(report_type)
        if not chat_ids:
            print(f'[Telegram] Sin destinatarios para tipo={report_type!r} — omitiendo')
            return False

        url     = f'https://api.telegram.org/bot{self.telegram_token}/sendMessage'
        success = 0
        for chat_id in chat_ids:
            try:
                resp = requests.post(
                    url,
                    json={'chat_id': chat_id, 'text': message, 'parse_mode': 'HTML'},
                    timeout=10,
                )
                data = resp.json()
                if data.get('ok'):
                    success += 1
                    print(f'[Telegram] Enviado a {chat_id}')
                else:
                    print(f'[Telegram] Error en {chat_id}: {data.get("description", resp.text[:120])}')
            except Exception as e:
                print(f'[Telegram] Excepción en {chat_id}: {e}')
        return success > 0

    # ── WhatsApp CallMeBot ─────────────────────────────────────────────────────

    def send_whatsapp_callmebot(self, message: str, report_type: str | None = None) -> bool:
        """Envía WhatsApp via CallMeBot (gratuito, personal)."""
        numbers = self._callmebot_numbers(report_type)
        if not numbers:
            print('[CallMeBot] No configurado — omitiendo')
            return False

        success = 0
        for entry in numbers:
            try:
                resp = requests.get(
                    'https://api.callmebot.com/whatsapp.php',
                    params={'phone': entry['phone'], 'text': message, 'apikey': entry['apikey']},
                    timeout=15,
                )
                if resp.status_code == 200 and 'Message Sent' in resp.text:
                    success += 1
                    print(f'[CallMeBot] Enviado a {entry["phone"]}')
                else:
                    print(f'[CallMeBot] Error en {entry["phone"]}: {resp.text[:120]}')
            except Exception as e:
                print(f'[CallMeBot] Excepción en {entry["phone"]}: {e}')
        return success > 0

    # ── WhatsApp Meta ──────────────────────────────────────────────────────────

    def send_whatsapp_meta(self, message: str) -> bool:
        """Envía WhatsApp via Meta Business API (oficial, de pago)."""
        if not self.wa_meta_token or not self.wa_meta_phone_id or not self.wa_meta_recipients:
            print('[Meta WhatsApp] No configurado — omitiendo')
            return False

        url     = f'https://graph.facebook.com/v17.0/{self.wa_meta_phone_id}/messages'
        headers = {'Authorization': f'Bearer {self.wa_meta_token}', 'Content-Type': 'application/json'}
        success = 0
        for recipient in self.wa_meta_recipients:
            try:
                resp = requests.post(url, headers=headers, json={
                    'messaging_product': 'whatsapp',
                    'to': recipient,
                    'type': 'text',
                    'text': {'body': message},
                }, timeout=15)
                if resp.status_code == 200:
                    success += 1
                    print(f'[Meta WhatsApp] Enviado a {recipient}')
                else:
                    print(f'[Meta WhatsApp] Error en {recipient}: {resp.text[:120]}')
            except Exception as e:
                print(f'[Meta WhatsApp] Excepción en {recipient}: {e}')
        return success > 0

    # ── Dispatcher WhatsApp ────────────────────────────────────────────────────

    def send_whatsapp(self, message: str, report_type: str | None = None) -> bool:
        """Intenta todos los proveedores de WhatsApp configurados."""
        results = []
        if self._callmebot_numbers(report_type):
            results.append(self.send_whatsapp_callmebot(message, report_type))
        if self.wa_meta_token and self.wa_meta_phone_id:
            results.append(self.send_whatsapp_meta(message))
        if not results:
            print('[WhatsApp] Ningún proveedor configurado — omitiendo')
            return False
        return any(results)

    # ── Broadcast: envía por todos los canales ─────────────────────────────────

    def broadcast(self, subject: str, text: str, html: str | None = None,
                  telegram_text: str | None = None,
                  whatsapp_text: str | None = None,
                  report_type: str | None = None) -> list[str]:
        """
        Envía por todos los canales configurados.
        Retorna lista de canales que tuvieron éxito.
        """
        sent = []
        if self.send_email(subject, text, html, report_type):
            sent.append('Email')
        if self.send_telegram(telegram_text or text, report_type):
            sent.append('Telegram')
        if self.send_whatsapp(whatsapp_text or text, report_type):
            sent.append('WhatsApp')
        return sent

    # ── Formateo de mensajes de stock ──────────────────────────────────────────

    def format_low_stock_message(self, new_products: list,
                                  total_low_count: int | None = None) -> tuple:
        """
        Retorna (text_message, html_message, telegram_message) para alertas de stock.

        new_products     — productos que acaban de entrar en stock bajo (1 o más).
        total_low_count  — total de productos actualmente en bajo stock (para el link).
        """
        if not new_products:
            return None, None, None

        timestamp = datetime.now().strftime('%d/%m/%Y %H:%M')
        base_url  = os.getenv('APP_BASE_URL', '').rstrip('/')
        stock_url = f'{base_url}/signage' if base_url else None

        others = (total_low_count or len(new_products)) - len(new_products)
        long_lead_count = sum(1 for p in new_products if p.get('is_long_lead'))

        # ── Texto plano (WhatsApp) ─────────────────────────────────────────
        if len(new_products) == 1:
            p    = new_products[0]
            ll   = p.get('is_long_lead', False)
            name = f'{p["name"]} — {p["variant"]}' if p.get('variant') else p['name']
            text = (
                f'{"🔴" if ll else "🟠"} STOCK BAJO{"  ⚠️ LONG LEAD ITEM" if ll else ""} — {name}\n'
                f'📦 Actual: {p["qty_available"]:.0f}'
                f'  |  Mín: {p["reordering_min_qty"]:.0f}'
                f'  |  Máx: {p["reordering_max_qty"]:.0f}\n'
            )
        else:
            long_lead_count = sum(1 for p in new_products if p.get('is_long_lead'))
            text = f'🚨 STOCK BAJO — {len(new_products)} productos nuevos'
            if long_lead_count:
                text += f' ({long_lead_count} Long Lead)'
            text += '\n'
            for p in new_products:
                ll    = p.get('is_long_lead', False)
                emoji = '🔴' if ll else '🟠'
                name  = f'{p["name"]} — {p["variant"]}' if p.get('variant') else p['name']
                text += f'{emoji} {name}{"  ⚠️" if ll else ""}: {p["qty_available"]:.0f} / mín {p["reordering_min_qty"]:.0f} / máx {p["reordering_max_qty"]:.0f}\n'

        if others > 0:
            text += f'\n+{others} producto(s) más en bajo stock.'
        if stock_url:
            text += f'\n🔗 Ver stock: {stock_url}'

        # ── Telegram HTML ──────────────────────────────────────────────────
        if len(new_products) == 1:
            p     = new_products[0]
            ll    = p.get('is_long_lead', False)
            emoji = '🔴' if ll else '🟠'
            name  = f'{p["name"]} — {p["variant"]}' if p.get('variant') else p['name']
            telegram = (
                f'{emoji} <b>Stock bajo: {name}</b>'
                f'{" — <i>Long Lead Item</i>" if ll else ""}\n'
                f'📦 <code>{p["qty_available"]:.0f}</code>'
                f' / mín <code>{p["reordering_min_qty"]:.0f}</code>'
                f' / máx <code>{p["reordering_max_qty"]:.0f}</code>'
            )
        else:
            telegram = f'🚨 <b>{len(new_products)} productos en stock bajo</b>\n'
            for p in new_products:
                ll    = p.get('is_long_lead', False)
                emoji = '🔴' if ll else '🟠'
                name  = f'{p["name"]} — {p["variant"]}' if p.get('variant') else p['name']
                telegram += (
                    f'{emoji} <b>{name}</b>'
                    f'{" ⚠️" if ll else ""}: '
                    f'<code>{p["qty_available"]:.0f}</code>'
                    f' / mín <code>{p["reordering_min_qty"]:.0f}</code>'
                    f' / máx <code>{p["reordering_max_qty"]:.0f}</code>\n'
                )

        if others > 0:
            telegram += f'\n<i>+{others} producto(s) más en bajo stock.</i>'
        if stock_url:
            telegram += f'\n🔗 <a href="{stock_url}">Ver todos</a>'

        # ── Email HTML ─────────────────────────────────────────────────────
        rows = ''
        for p in new_products:
            is_ll   = p.get('is_long_lead', False)
            variant = f'<br><small style="color:#718096">{p["variant"]}</small>' if p.get('variant') else ''
            ll_tag  = '<br><small style="color:#d32f2f;font-weight:600">⚠️ Long Lead Item</small>' if is_ll else ''
            bg      = '#fff5f5' if is_ll else '#ebf8ff'
            rows += f"""
                <tr style="background:{bg}">
                    <td style="padding:8px">{p['name']}{variant}{ll_tag}</td>
                    <td style="padding:8px;text-align:center">{p['qty_available']:.2f}</td>
                    <td style="padding:8px;text-align:center">{p['reordering_min_qty']:.2f}</td>
                    <td style="padding:8px;text-align:center">{p['reordering_max_qty']:.2f}</td>
                </tr>"""

        others_note = ''
        if others > 0:
            others_note = f'<p style="color:#666">Además hay <strong>{others}</strong> producto(s) más en bajo stock.</p>'

        link_note = ''
        if stock_url:
            link_note = f'<p><a href="{stock_url}" style="color:#667eea">🔗 Ver todos los productos en bajo stock</a></p>'

        html = f"""<html><body>
            <h2 style="color:{'#d32f2f' if long_lead_count else '#ff9800'}">
                {'🔴 Stock Bajo — Long Lead Items' if long_lead_count else '🟠 Nuevo producto en stock bajo'}
            </h2>
            {'<p style="background:#fff5f5;padding:8px 12px;border-left:4px solid #d32f2f;border-radius:4px;color:#c62828"><strong>⚠️ ' + str(long_lead_count) + ' producto(s) con etiqueta Long Lead Item requieren atención prioritaria.</strong></p>' if long_lead_count else ''}
            <p><strong>Fecha:</strong> {timestamp}</p>
            <table border="1" style="border-collapse:collapse;width:100%">
                <thead style="background:#f5f5f5">
                    <tr>
                        <th style="padding:10px;text-align:left">Producto</th>
                        <th style="padding:10px">Stock Actual</th>
                        <th style="padding:10px">Stock Mínimo</th>
                        <th style="padding:10px">Stock Máximo</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            {others_note}
            {link_note}
        </body></html>"""

        return text, html, telegram
