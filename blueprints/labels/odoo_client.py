"""
Cliente de Odoo via XML-RPC.

Uso básico:
    from odoo_client import OdooClient

    odoo = OdooClient(
        url='http://192.168.1.160:8070/',
        db='ppg',
        username='admin',
        password='tu_password',
    )

    # Buscar clientes
    clientes = odoo.search_partners('Empresa ABC')

    # Buscar productos
    productos = odoo.search_products('cepillo')

    # Detalle de un cliente
    cliente = odoo.get_partner(42)

    # Detalle de un producto (incluye imagen en base64)
    producto = odoo.get_product(17)
"""

import logging
import xmlrpc.client
from functools import cached_property

logger = logging.getLogger(__name__)


class OdooClient:
    """
    Wrapper ligero sobre la API XML-RPC de Odoo.
    La autenticación se hace una sola vez y se reutiliza (cached_property).
    """

    def __init__(self, url: str, db: str, username: str, password: str):
        # Asegura que la URL no tenga barra al final para evitar doble slash
        self.url      = url.rstrip('/')
        self.db       = db
        self.username = username
        self.password = password

    # ── Conexión ────────────────────────────────────────────────────────────

    @cached_property
    def _uid(self) -> int:
        """Autentica y devuelve el uid. Se ejecuta solo la primera vez."""
        common = xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/common')
        uid = common.authenticate(self.db, self.username, self.password, {})
        if not uid:
            raise ConnectionError(
                f'No se pudo autenticar en Odoo ({self.url}) '
                f'con el usuario "{self.username}"'
            )
        return uid

    @cached_property
    def _models(self):
        """Proxy al endpoint de modelos. Se crea solo la primera vez."""
        return xmlrpc.client.ServerProxy(f'{self.url}/xmlrpc/2/object')

    def _execute(self, model: str, method: str, *args, **kwargs):
        """Atajo para execute_kw."""
        return self._models.execute_kw(
            self.db, self._uid, self.password,
            model, method,
            list(args),
            kwargs,
        )

    # ── Clientes (res.partner) ───────────────────────────────────────────────

    def search_partners(self, query: str, limit: int = 20) -> list[dict]:
        """
        Busca socios/clientes cuyo nombre contenga `query`.
        Devuelve lista de {'id': int, 'name': str}.
        """
        try:
            return self._execute(
                'res.partner', 'search_read',
                [['name', 'ilike', query]],
                fields=['id', 'name'],
                limit=limit,
            )
        except Exception:
            logger.exception(f'Error buscando partners con query="{query}"')
            return []

    def get_partner(self, partner_id: int) -> dict | None:
        """
        Devuelve el detalle de un socio/cliente.
        Campos: id, name, phone, street, street2, city, zip, email.
        """
        try:
            res = self._execute(
                'res.partner', 'read',
                [partner_id],
                fields=['id', 'name', 'phone', 'street', 'street2', 'city', 'zip', 'email'],
            )
            return res[0] if res else None
        except Exception:
            logger.exception(f'Error obteniendo partner id={partner_id}')
            return None

    # ── Productos (product.product) ──────────────────────────────────────────

    def search_products(self, query: str, limit: int = 20) -> list[dict]:
        """
        Busca productos cuyo nombre contenga `query`.
        Devuelve lista de {'id': int, 'display_name': str}.
        """
        try:
            results = self._execute(
                'product.product', 'name_search',
                query,
                limit=limit,
            )
            return [{'id': pid, 'display_name': name} for pid, name in results]
        except Exception:
            logger.exception(f'Error buscando productos con query="{query}"')
            return []

    def get_product(self, product_id: int) -> dict | None:
        """
        Devuelve el detalle de un producto.
        Campos: id, display_name, image_1920 (base64 str o None).
        """
        try:
            res = self._execute(
                'product.product', 'read',
                [product_id],
                fields=['id', 'display_name', 'image_1920'],
            )
            if not res:
                return None
            p = res[0]
            return {
                'id':           p['id'],
                'display_name': p['display_name'],
                'image_1920':   p.get('image_1920'),
            }
        except Exception:
            logger.exception(f'Error obteniendo producto id={product_id}')
            return None

    # ── Método genérico (para consultas personalizadas) ──────────────────────

    def query(self, model: str, domain: list, fields: list,
              limit: int = 100, order: str = '') -> list[dict]:
        """
        Búsqueda genérica sobre cualquier modelo de Odoo.

        Ejemplo:
            odoo.query(
                model='mrp.production',
                domain=[['state', 'in', ['confirmed', 'progress']]],
                fields=['name', 'product_id', 'product_qty'],
                limit=50,
            )
        """
        kwargs = {'fields': fields, 'limit': limit}
        if order:
            kwargs['order'] = order
        try:
            return self._execute(model, 'search_read', domain, **kwargs)
        except Exception:
            logger.exception(f'Error en query genérica sobre modelo "{model}"')
            return []
