from django.apps import AppConfig


class OpportunitiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "opportunities"
    verbose_name = "Opportunities"

    def ready(self):
        # Enforce persisted-state immutability for children of published revisions,
        # including bulk/queryset deletes where model.delete() is bypassed.
        from . import signals  # noqa: F401
        from .runtime_authorization import install_opportunity_authorization_policy

        install_opportunity_authorization_policy()
