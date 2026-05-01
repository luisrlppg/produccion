from .routes.personal import personal_bp
from .routes.company import company_bp
from .routes.production import production_bp
from .routes.admin import admin_bp

__all__ = ['personal_bp', 'company_bp', 'production_bp', 'admin_bp']
