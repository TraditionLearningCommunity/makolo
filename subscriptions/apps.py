from django.apps import AppConfig


class SubscriptionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "subscriptions"
    verbose_name = "Subscriptions"

    def import_models(self):
        """Load S2 runtime models in the normal Django model-import phase.

        S1 intentionally kept its catalogue models in ``subscriptions.models``.
        S2 lives in a separate module to keep that file stable while both sets
        remain models of the same bounded context. Re-export the runtime models
        so callers continue to use ``subscriptions.models`` as the canonical
        import surface.
        """
        super().import_models()
        from . import runtime_models

        for name in ("Subscription", "SubscriptionItem", "EntitlementGrant"):
            setattr(self.models_module, name, getattr(runtime_models, name))

    def ready(self):
        from . import signals  # noqa: F401
