from django.apps import AppConfig


class AutomationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "automation"
    verbose_name = "Makolo Autopilot"

    def ready(self):
        from . import crm_signals  # noqa: F401
