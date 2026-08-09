from django.apps import AppConfig


class PromotionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "promotions"
    verbose_name = "Promotions & codes"

    def ready(self):
        from . import signals  # noqa: F401
