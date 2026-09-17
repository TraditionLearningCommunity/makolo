from django.apps import AppConfig


class ProspectorStorageConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "prospector.django_app"
    label = "prospector_storage"
    verbose_name = "Prospector Storage"
