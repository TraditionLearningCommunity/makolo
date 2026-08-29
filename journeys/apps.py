from django.apps import AppConfig


class JourneysConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "journeys"
    verbose_name = "Démarches"

    def ready(self):
        from .service_authorization import install_service_authorization_policy
        install_service_authorization_policy()
