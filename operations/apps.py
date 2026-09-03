from django.apps import AppConfig


class OperationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "operations"
    verbose_name = "Makolo Operations"

    def import_models(self):
        super().import_models()
        from . import checkpoint_models, placement_models

        for name in ("PlacementPlan", "PlacementUnit", "PlacementAssignment"):
            setattr(self.models_module, name, getattr(placement_models, name))
        for name in ("CheckpointStatus", "OccurrenceCheckpoint", "CheckpointAssignment", "CheckpointObservation"):
            setattr(self.models_module, name, getattr(checkpoint_models, name))
