from django.apps import AppConfig


class TicketsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tickets"

    def ready(self):
        from .legacy_compat import install_ticket_type_legacy_compat
        from .order_legacy_compat import install_ticket_order_legacy_compat

        install_ticket_type_legacy_compat()
        install_ticket_order_legacy_compat()
        from . import journey_access_bridge  # noqa: F401
        from . import commerce_capacity_bridge  # noqa: F401
        from . import event_capacity_bridge  # noqa: F401
        from . import commerce_projection_signals  # noqa: F401
        from . import access_projection_signals  # noqa: F401
