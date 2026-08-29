"""Django settings for Makolo.

The stable settings body lives in ``base_settings`` so new bounded contexts can
be registered without changing deployment entry points or maintaining a second
runtime settings module.
"""

import os
from urllib.parse import urlparse

from django.core.exceptions import ImproperlyConfigured

from .base_settings import *  # noqa: F401,F403

INSTALLED_APPS = [
    *INSTALLED_APPS,
    "transport.apps.TransportConfig",
    "requirements.apps.RequirementsConfig",
    "services.apps.ServicesConfig",
    "opportunities.apps.OpportunitiesConfig",
    "subscriptions.apps.SubscriptionsConfig",
]

# MapLibre is the renderer. Tile data remains an explicit, replaceable runtime
# configuration and does not require a Mapbox/Google token.
MAP_TILE_URL = os.environ.get(
    "MAP_TILE_URL",
    "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
).strip()
MAP_TILE_ATTRIBUTION = os.environ.get(
    "MAP_TILE_ATTRIBUTION",
    '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
).strip()
try:
    MAP_TILE_MAX_ZOOM = int(os.environ.get("MAP_TILE_MAX_ZOOM", "19"))
except ValueError as exc:
    raise ImproperlyConfigured("MAP_TILE_MAX_ZOOM doit être un entier.") from exc
if not 0 <= MAP_TILE_MAX_ZOOM <= 24:
    raise ImproperlyConfigured("MAP_TILE_MAX_ZOOM doit être compris entre 0 et 24.")

_tile_url = urlparse(MAP_TILE_URL)
if _tile_url.scheme not in {"http", "https"} or not _tile_url.netloc:
    raise ImproperlyConfigured("MAP_TILE_URL doit être une URL HTTP(S) absolue.")
_tile_origin = f"{_tile_url.scheme}://{_tile_url.netloc}"

MAKOLO_CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "base-uri 'self'",
        f"connect-src 'self' {_tile_origin}",
        "font-src 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
        "frame-src 'none'",
        f"img-src 'self' data: blob: {_tile_origin}",
        "media-src 'self' blob:",
        "object-src 'none'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "worker-src 'self' blob:",
    ]
)
MAKOLO_PERMISSIONS_POLICY = "camera=(self), microphone=(), geolocation=(self)"
