from django.apps import AppConfig


class InterpreterStorageConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "interpreter.django_app"
    label = "interpreter_storage"
    verbose_name = "Interpreter Storage"
