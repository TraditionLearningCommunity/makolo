from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "notifications"

    def ready(self):
        from . import domain_event_consumer  # noqa: F401
        from . import services_domain_event_consumer  # noqa: F401
