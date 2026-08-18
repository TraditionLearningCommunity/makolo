from django.apps import AppConfig


class EventsConfig(AppConfig):
    name = "events"

    def ready(self):
        from .legacy_compat import install_event_legacy_compat

        install_event_legacy_compat()
