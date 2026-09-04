from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .credential_models import Credential


@receiver(pre_delete, sender=Credential)
def prevent_credential_history_delete(sender, instance, **kwargs):
    raise ValidationError(
        "Un Credential délivré appartient à l’historique Trust et ne peut pas être supprimé."
    )
