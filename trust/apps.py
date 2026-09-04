from django.apps import AppConfig


class TrustConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "trust"
    verbose_name = "Trust & Quality"

    def import_models(self):
        super().import_models()
        # Credential lives in a focused module to preserve the existing M4
        # models file while remaining part of the canonical Trust app registry.
        from . import credential_models  # noqa: F401

    def ready(self):
        # Trust evidence reuses the canonical private Journey artifact storage:
        # it lives outside MEDIA_ROOT and cannot expose a storage URL. The
        # assignment is paired with migration state so makemigrations sees the
        # same storage contract without creating a second storage backend.
        from journeys.storage import private_artifact_storage

        from .models import TrustEvidence

        TrustEvidence._meta.get_field("file").storage = private_artifact_storage

        # Register lifecycle notifications. Payloads are deliberately minimal:
        # no evidence, report body, reviewer note or other sensitive content.
        from . import signals  # noqa: F401
