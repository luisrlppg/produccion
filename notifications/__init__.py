"""
Módulo de notificaciones unificado — PPG
Soporta Email (SMTP), Telegram (Bot API), WhatsApp (CallMeBot y Meta).

Uso básico:
    from notifications import NotificationManager
    nm = NotificationManager()
    nm.send_telegram("Hola", report_type='production')

Variables de entorno:
    TELEGRAM_BOT_TOKEN          — token del bot (compartido por todos los tipos)
    TELEGRAM_<TYPE>_RECIPIENTS  — chat_ids separados por coma
    WHATSAPP_<TYPE>_RECIPIENTS  — numero:apikey,numero2:apikey2  (CallMeBot)
    WHATSAPP_TOKEN / WHATSAPP_PHONE_ID / WHATSAPP_RECIPIENTS  — Meta API (global)
    SMTP_SERVER / SMTP_PORT / EMAIL_USER / EMAIL_PASSWORD
    EMAIL_RECIPIENTS / <TYPE>_EMAIL_RECIPIENTS
"""

from .manager import NotificationManager

__all__ = ['NotificationManager']
