from django.apps import AppConfig


class PartnersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "partners"

    def ready(self):
        from . import notification_signals, signals  # noqa: F401
