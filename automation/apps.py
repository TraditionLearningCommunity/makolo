from django.apps import AppConfig


class AutomationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "automation"

    def ready(self):
        # R3 keeps its cursor model in Automation's operational boundary. Importing
        # it here registers the auxiliary model without creating a Preparation app.
        from . import proactive_models  # noqa: F401
        from .service_contracts import install_service_automation_contracts

        install_service_automation_contracts()
        from . import crm_signals  # noqa: F401
        from . import domain_event_consumer  # noqa: F401
        from . import proactive_domain_event_consumer  # noqa: F401
