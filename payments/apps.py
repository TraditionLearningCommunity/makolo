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
        # F4 models live in a dedicated module to keep the F1-F3 model file
        # stable while remaining registered under the canonical payments app.
        from . import f4_models  # noqa: F401
        from . import commerce_bridge  # noqa: F401
        from . import financial_signals  # noqa: F401
        from . import f4_signals  # noqa: F401
