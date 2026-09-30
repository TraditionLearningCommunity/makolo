from django.apps import AppConfig


class ObtentionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "obtention"
    verbose_name = "Obtention"

    def ready(self):
        # Register the vertical-specific Readiness contributor without making
        # Readiness own Obtention truth.
        from . import readiness  # noqa: F401
