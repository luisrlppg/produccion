# PPG Unified - Project Context

## Overview
PPG Unified is a Flask-based web application for managing production reports, manufacturing orders from Odoo, and inventory monitoring for a manufacturing company.

## Tech Stack
- **Backend**: Python 3.x, Flask
- **Database**: SQLite (ppg.db)
- **Frontend**: HTML, CSS (Bootstrap 5), JavaScript (vanilla)
- **External Integration**: Odoo ERP via XML-RPC
- **Real-time**: Server-Sent Events (SSE) for live display updates
- **Notifications**: Email (SMTP), Telegram, WhatsApp (Meta API), CallMeBot

## Project Structure

```
ppg-unified/
├── app.py                      # Main Flask application entry point
├── auth.py                     # Authentication decorators and credential checking
├── database.py                 # SQLite operations and queries
├── utils.py                    # Utility functions (i18n, formatting, JSON handling)
├── check_stock.py              # CLI script for stock monitoring
├── requirements.txt            # Python dependencies
├── .env                        # Environment variables (not in git)
├── .env.example                # Environment variables template
│
├── blueprints/                 # Flask blueprints (modular routes)
│   ├── labels/                 # Label generation module
│   │   ├── __init__.py
│   │   ├── routes.py
│   │   └── odoo_client.py
│   ├── reports/                # Production reports module
│   │   ├── __init__.py
│   │   ├── production_sections.py  # Single source of truth for production sections
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── admin.py        # Admin panel routes (view, edit, delete, CSV export)
│   │       ├── production.py   # Production report submission
│   │       ├── personal.py     # Personal reports
│   │       └── company.py      # Company reports
│   └── signage/                # Manufacturing display & stock monitor
│       ├── __init__.py
│       ├── routes.py           # Signage routes (panel, display, SSE, stock)
│       ├── odoo_client.py      # Odoo XML-RPC client
│       └── stock_monitor.py    # Stock monitoring and notifications
│
├── notifications/              # Notification system
│   ├── __init__.py
│   └── manager.py              # Multi-channel notification manager
│
├── templates/                  # Jinja2 templates
│   ├── base.html               # Base template with common styles
│   ├── index.html              # Home page
│   ├── login.html              # Login page
│   ├── reportes.html           # Reports hub
│   ├── labels/                 # Label generation templates
│   ├── reports/                # Production report templates
│   │   ├── panel_dashboard.html
│   │   ├── panel_production.html
│   │   ├── panel_production_view.html
│   │   ├── panel_production_stats.html
│   │   ├── edit_production.html
│   │   ├── report_form.html
│   │   └── partials/           # Reusable template partials
│   │       └── production/
│   │           ├── machines.html
│   │           ├── product_rows.html
│   │           ├── deliveries.html
│   │           ├── notes.html
│   │           └── scripts.html
│   └── signage/                # Manufacturing display templates
│       ├── base.html           # Signage base template with navbar
│       ├── index.html          # Panel for selecting orders (3 tabs: production, stock, sales)
│       └── display.html        # Public display screen (SSE-powered, no auth)
│
├── static/                     # Static assets
│   ├── css/
│   │   ├── labels.css
│   │   └── signage.css         # Signage styles (production list & display)
│   └── fixed.png
│
├── data/                       # Data storage
│   ├── ppg.db                  # SQLite database
│   ├── production_details.json # Detailed production data
│   ├── display_products.json   # Selected products for display
│   ├── known_low_stock.json    # Tracked low stock items
│   ├── *.csv                   # CSV exports
│   └── migrations/             # SQL migration scripts
│       ├── 001_initial.sql
│       ├── 002_produccion_por_hora.sql
│       ├── 003_add_perforado.sql
│       └── 004_section_totals.sql
│
├── uploads/                    # User-uploaded files (photos)
└── scripts/                    # Utility scripts
    └── recalculate_section_totals.py
```

## Key Features

### 1. Production Reports
- **Form submission**: Workers submit daily production reports with:
  - Shift info (name, shift, date, worker count)
  - Machine production (3 machines: quantity, brush type, color)
  - Product sections (Ensamble, Ensartado, Pegado, Perforado) - dynamic rows
  - Deliveries (customer, description)
  - Additional notes
- **Automatic calculations**: Production per person per hour
- **Storage**: SQLite + JSON for detailed product breakdowns
- **Notifications**: Multi-channel broadcast on submission
- **Admin panel**: View, edit, delete reports; export to CSV

### 2. Manufacturing Display (Signage)
- **Panel (`/signage`)**: 
  - Load manufacturing orders from Odoo
  - Select priority orders from 3 categories (Inyección, Ensamble, Cepillo)
  - Save selection → pushes to display via SSE
  - Stock monitor tab with low stock alerts
  - Sales orders tab with delivery status
- **Display (`/signage/display`)**: 
  - Public screen (no auth)
  - Shows selected orders in vertical list
  - Dynamic font sizing (scales to fit all items on screen)
  - Real-time updates via SSE
  - Color-coded by category

### 3. Stock Monitoring
- **Automatic checks**: Compares Odoo stock vs reordering rules
- **Smart notifications**: Only alerts on new low stock items
- **Long-lead tracking**: Flags critical items with "long lead" tag
- **Manual triggers**: Force check and send report
- **Multi-channel**: Email, Telegram, WhatsApp

### 4. Odoo Integration
- **XML-RPC client**: Connects to Odoo ERP
- **Manufacturing orders**: Fetches active orders (confirmed, in progress, to close)
- **Product categories**: Auto-categorizes by product category name
- **Stock levels**: Real-time inventory data
- **Sales orders**: Order status, delivery tracking, stock availability

## Database Schema

### production_reports
```sql
- id (PRIMARY KEY)
- nombre, turno, fecha, trabajadores
- maquina1_cantidad, maquina1_tipo, maquina1_color
- maquina2_cantidad, maquina2_tipo, maquina2_color
- maquina3_cantidad, maquina3_tipo, maquina3_color
- ensamble, ensartado, pegado, perforado (TEXT - formatted product lists)
- total_ensamble, total_ensartado, total_pegado, total_perforado (INTEGER)
- entregas (TEXT - formatted deliveries)
- produccion_personal, produccion_maquinas, produccion_total
- produccion_por_persona_hora (REAL)
- notas, timestamp
```

### personal_reports, company_reports
```sql
- id (PRIMARY KEY)
- item_name, location
- failure_description, additional_info
- photo_path, timestamp
```

## Configuration

### Environment Variables (.env)
```bash
# App
APP_USERNAME=admin
APP_PASSWORD=ppg1234
APP_BASE_URL=http://localhost:5000
SECRET_KEY=your-secret-key

# Odoo
ODOO_URL=http://192.168.1.160:8070/
ODOO_DB=ppg
ODOO_USERNAME=admin
ODOO_PASSWORD=odooppg

# Email (SMTP)
EMAIL_USER=your-email@gmail.com
EMAIL_PASSWORD=your-app-password
EMAIL_RECIPIENTS=recipient1@example.com,recipient2@example.com

# Telegram
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_CHAT_IDS=chat_id1,chat_id2
TELEGRAM_STOCK_RECIPIENTS=chat_id1,chat_id2

# WhatsApp (Meta Business API)
WHATSAPP_TOKEN=your-whatsapp-token
WHATSAPP_PHONE_ID=your-phone-id
WHATSAPP_RECIPIENTS=+521234567890,+529876543210

# CallMeBot (WhatsApp alternative)
CALLMEBOT_NUMBERS=+521234567890:apikey1,+529876543210:apikey2
```

## Important Patterns

### Production Sections (Single Source of Truth)
`blueprints/reports/production_sections.py` defines all production sections:
```python
PRODUCTION_SECTIONS = [
    {
        'key': 'ensamble',           # DB column name
        'total_col': 'total_ensamble',  # DB total column
        'label': 'Ensamble',         # Display label
        'css_prefix': 'assembly',    # CSS/JS prefix
        'json_key': 'ensamble',      # JSON key
        'csv_label': 'Ensamble',     # CSV header
    },
    # ... more sections
]
```
To add a section: update this file + run SQL migration.

### SSE (Server-Sent Events)
Display screen connects to `/signage/events` and receives real-time updates when panel saves selection. No polling, no localStorage.

### Authentication
- Single session: `session['logged_in']`
- Decorator: `@login_required`
- Credentials in `.env`

### Notifications
`NotificationManager.broadcast()` sends to all configured channels:
```python
nm.broadcast(
    subject='Subject',
    text='Plain text',
    html='<html>...</html>',
    telegram_text='Telegram formatted',
    whatsapp_text='WhatsApp text',
    report_type='production'  # or 'stock'
)
```

## Common Tasks

### Add a new production section
1. Edit `blueprints/reports/production_sections.py`
2. Create migration: `ALTER TABLE production_reports ADD COLUMN <key> TEXT NOT NULL DEFAULT '';`
3. Add total column: `ALTER TABLE production_reports ADD COLUMN total_<key> INTEGER NOT NULL DEFAULT 0;`
4. Run migration
5. Templates auto-update (they loop over `PRODUCTION_SECTIONS`)

### Export CSV with correct encoding
CSV exports include UTF-8 BOM (`\ufeff`) for Excel compatibility.

### Test notifications
Use `/signage` → "Probar Notificaciones" button

### Monitor stock manually
Run: `python check_stock.py --force`

## Development

### Run locally
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your credentials
python app.py
```

### Database migrations
Place SQL files in `data/migrations/` with sequential numbering.

## Deployment Notes
- Uses SQLite (single file DB) - suitable for small teams
- SSE requires persistent connections - use gunicorn with gevent workers
- Static files served by Flask (consider nginx for production)
- No HTTPS in app - use reverse proxy (nginx/caddy)

## Recent Changes
- **Display redesign**: Vertical list layout with dynamic font sizing (no scroll, fits all items)
- **Panel improvements**: Toolbar moved to top, columns equal height
- **CSV fix**: UTF-8 BOM + proper headers to prevent HTML in downloads

## Troubleshooting

### CSV downloads show HTML
- Check authentication (login before downloading)
- Verify database has data
- Check browser console for errors

### Display not updating
- Check SSE connection in browser DevTools → Network
- Verify panel saved selection successfully
- Check server logs for SSE errors

### Odoo connection fails
- Verify ODOO_URL, ODOO_DB, credentials in .env
- Test connection: `python -c "from blueprints.signage.odoo_client import connect; print(connect())"`

### Notifications not sending
- Check `/signage` → notification status indicators
- Verify credentials in .env
- Test with "Probar Notificaciones" button

## Contact
For questions about this project, refer to the commit history or check the inline comments in the code.
