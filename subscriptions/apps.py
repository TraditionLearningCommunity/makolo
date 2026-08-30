from django.apps import AppConfig


class SubscriptionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "subscriptions"
    verbose_name = "Subscriptions"

    def import_models(self):
        """Load runtime and eligibility models during Django model import."""
        super().import_models()
        from . import eligibility_models, runtime_models

        for name in ("Subscription", "SubscriptionItem", "EntitlementGrant"):
            setattr(self.models_module, name, getattr(runtime_models, name))
        for name in ("PlanRequirement", "EntitlementRequirement"):
            setattr(self.models_module, name, getattr(eligibility_models, name))

    def ready(self):
        from . import signals  # noqa: F401
        from .evaluators import register_subscription_evaluators

        register_subscription_evaluators()
