from django.apps import AppConfig


class SharingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "sharing"
    verbose_name = "Partage"

    def ready(self):
        # P4 staging models live in a focused module but remain owned by the sharing app.
        from . import inbound_models  # noqa: F401
