import os

from django.apps import AppConfig
from django.conf import settings


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "payments"

    def ready(self):
        # Valeurs par défaut du module. Elles restent surchargeables depuis
        # settings.py ou override_settings dans les tests. Le sandbox n'est
        # jamais activé implicitement lorsque DEBUG=False.
        if not hasattr(settings, "PAYMENTS_SANDBOX_ENABLED"):
            settings.PAYMENTS_SANDBOX_ENABLED = bool(settings.DEBUG)
        if not hasattr(settings, "PAYMENTS_WEBHOOK_SECRET"):
            settings.PAYMENTS_WEBHOOK_SECRET = os.environ.get(
                "PAYMENTS_WEBHOOK_SECRET",
                "",
            )
        from . import commerce_bridge  # noqa: F401
