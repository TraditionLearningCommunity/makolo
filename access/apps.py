from django.apps import AppConfig


class AccessConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "access"
    verbose_name = "Accès"

    def ready(self):
        from . import signals  # noqa: F401
