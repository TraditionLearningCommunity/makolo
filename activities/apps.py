from django.apps import AppConfig


class ActivitiesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "activities"
    verbose_name = "Activities"

    def ready(self):
        # The involvement models are kept in a dedicated module to avoid
        # bloating the canonical Activity/Occurrence model file. Importing
        # them here registers them in the same Django app without duplicating
        # Activity or Occurrence truth.
        from . import involvement_models  # noqa: F401
