from django.apps import AppConfig


class PromotionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "promotions"
    verbose_name = "Promotions & codes"

    def ready(self):
        from . import canonical_models  # noqa: F401
        from . import canonical_admin  # noqa: F401
        from . import bridge  # noqa: F401
        from . import signals  # noqa: F401
