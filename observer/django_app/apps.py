from django.apps import AppConfig


class ObserverStorageConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "observer.django_app"
    label = "observer_storage"
    verbose_name = "Observer Storage"
