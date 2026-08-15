from django.apps import AppConfig


class AnalyticsAppConfig(AppConfig):
    name = "analytics_app"

    def ready(self):
        from . import domain_event_consumer  # noqa: F401
