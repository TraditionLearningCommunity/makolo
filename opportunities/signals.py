from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import OpportunityRequirement, OpportunityRevision, OpportunityZone


def _published_revision(revision_id):
    return bool(
        revision_id
        and OpportunityRevision.objects.filter(
            pk=revision_id,
            published_at__isnull=False,
        ).exists()
    )


@receiver(pre_delete, sender=OpportunityZone)
def protect_published_revision_zone(sender, instance, **kwargs):
    if _published_revision(instance.revision_id):
        raise ValidationError("Les zones d’une révision publiée sont immuables.")


@receiver(pre_delete, sender=OpportunityRequirement)
def protect_published_revision_requirement(sender, instance, **kwargs):
    if _published_revision(instance.revision_id):
        raise ValidationError("Les Requirements d’une révision publiée sont immuables.")
