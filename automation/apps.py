from django.apps import AppConfig


class AutomationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "automation"

    def ready(self):
        from .service_contracts import install_service_automation_contracts

        install_service_automation_contracts()
        from . import crm_signals  # noqa: F401
        from . import domain_event_consumer  # noqa: F401
