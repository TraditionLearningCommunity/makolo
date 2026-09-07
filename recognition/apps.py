from django.apps import AppConfig


class RecognitionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "recognition"
    verbose_name = "Recognition"

    def ready(self):
        from . import domain_event_consumer  # noqa: F401
        from . import immutability  # noqa: F401
