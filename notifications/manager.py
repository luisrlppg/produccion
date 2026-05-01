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
        if self.send_whatsapp(text, report_type):
            sent.append('WhatsApp')
        return sent

    # ── Formateo de mensajes de stock ──────────────────────────────────────────

    def format_low_stock_message(self, low_stock_products: list) -> tuple:
        """
        Retorna (text_message, html_message, telegram_message) para alertas de stock.
        """
        if not low_stock_products:
            return None, None, None

        timestamp = datetime.now().strftime('%d/%m/%Y %H:%M')

        # Texto plano
        text = f'🚨 ALERTA DE STOCK BAJO - {timestamp}\n\nProductos por debajo del mínimo:\n\n'
        for p in low_stock_products:
            text += (
                f"• {p['name']}\n"
                f"  Actual: {p['qty_available']:.2f}  |  "
                f"Mínimo: {p['reordering_min_qty']:.2f}  |  "
                f"Dif: {p['difference']:.2f}\n\n"
            )
        text += 'Es necesario programar la fabricación.'

        # Telegram HTML
        telegram = f'🚨 <b>ALERTA DE STOCK BAJO</b>\n📅 <i>{timestamp}</i>\n\n'
        for i, p in enumerate(low_stock_products, 1):
            emoji = '🔴' if p['difference'] < -10 else ('🟡' if p['difference'] < -5 else '🟠')
            telegram += (
                f"{emoji} <b>{i}. {p['name']}</b>\n"
                f"   📦 Actual: <code>{p['qty_available']:.2f}</code>\n"
                f"   📊 Mínimo: <code>{p['reordering_min_qty']:.2f}</code>\n"
                f"   ⚠️ Diferencia: <code>{p['difference']:.2f}</code>\n\n"
            )
        telegram += '⚡ <b>Programar fabricación de estos productos.</b>'

        # Email HTML
        rows = ''
        for p in low_stock_products:
            if p['difference'] < -10:
                status, color = 'Crítico', '#d32f2f'
            elif p['difference'] < -5:
                status, color = 'Urgente', '#ff9800'
            else:
                status, color = 'Bajo', '#2196f3'
            rows += f"""
                <tr>
                    <td style="padding:8px">{p['name']}</td>
                    <td style="padding:8px;text-align:center">{p['qty_available']:.2f}</td>
                    <td style="padding:8px;text-align:center">{p['reordering_min_qty']:.2f}</td>
                    <td style="padding:8px;text-align:center;color:#d32f2f"><strong>{p['difference']:.2f}</strong></td>
                    <td style="padding:8px;text-align:center;color:{color}"><strong>{status}</strong></td>
                </tr>"""

        html = f"""<html><body>
            <h2 style="color:#d32f2f">🚨 ALERTA DE STOCK BAJO</h2>
            <p><strong>Fecha:</strong> {timestamp}</p>
            <table border="1" style="border-collapse:collapse;width:100%">
                <thead style="background:#f5f5f5">
                    <tr>
                        <th style="padding:10px;text-align:left">Producto</th>
                        <th style="padding:10px">Stock Actual</th>
                        <th style="padding:10px">Stock Mínimo</th>
                        <th style="padding:10px">Diferencia</th>
                        <th style="padding:10px">Estado</th>
                    </tr>
                </thead>
                <tbody>{rows}</tbody>
            </table>
            <p style="margin-top:20px;color:#d32f2f">
                <strong>⚠️ Es necesario programar la fabricación de estos productos.</strong>
            </p>
        </body></html>"""

        return text, html, telegram
