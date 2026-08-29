from django.apps import AppConfig


class ServicesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "services"
    verbose_name = "Makolo Services"

    def ready(self):
        from .runtime_authorization import install_services_runtime_authorization

        install_services_runtime_authorization()
