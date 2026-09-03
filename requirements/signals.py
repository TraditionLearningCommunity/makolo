from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import RequirementReuseApplication, RequirementReusePolicy


@receiver(pre_delete, sender=RequirementReusePolicy)
def protect_published_reuse_policy_delete(sender, instance, **kwargs):
    if instance.requirement.revision.published_at is not None:
        raise ValidationError("La policy d’un Requirement publié ne peut pas être supprimée.")


@receiver(pre_delete, sender=RequirementReuseApplication)
def protect_reuse_application_delete(sender, instance, **kwargs):
    raise ValidationError("Un audit Trusted Reuse ne peut pas être supprimé silencieusement.")
