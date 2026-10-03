from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can

from .enums import PresentationState, VersionStatus, Visibility
from .models import ActivityPresentation


def _template_accessible(actor, version, activity):
    template = version.template
    if template.visibility == Visibility.PUBLIC:
        return True
    if template.owner_profile_id and template.owner_profile_id == getattr(actor, "pk", None):
        return True
    if template.owner_space_id and activity.space_id == template.owner_space_id:
        return can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity)
    return False


def _theme_accessible(actor, version, activity):
    theme = version.theme
    if theme.visibility == Visibility.PUBLIC:
        return True
    if theme.owner_profile_id and theme.owner_profile_id == getattr(actor, "pk", None):
        return True
    if theme.owner_space_id and activity.space_id == theme.owner_space_id:
        return can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity)
    return False


def ensure_activity_presentation_authority(actor, activity):
    if not getattr(actor, "is_authenticated", False) or not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity):
        raise PermissionDenied("Vous n’avez pas l’autorité requise pour gérer la Présentation de cette Activity.")


@transaction.atomic
def configure_activity_presentation(*, actor, activity, purpose, template_version, theme_version, occurrence=None, editorial_data=None, visual_overrides=None):
    ensure_activity_presentation_authority(actor, activity)
    if occurrence is not None and occurrence.activity_id != activity.pk:
        raise ValidationError({"occurrence": "L’Occurrence doit appartenir à l’Activity."})
    if template_version.status != VersionStatus.PUBLISHED or theme_version.status != VersionStatus.PUBLISHED:
        raise ValidationError("Seules des versions publiées peuvent être sélectionnées.")
    if not _template_accessible(actor, template_version, activity) or not _theme_accessible(actor, theme_version, activity):
        raise PermissionDenied("Ce modèle ou ce thème n’est pas disponible dans ce contexte.")
    lookup = {"activity": activity, "occurrence": occurrence, "purpose": purpose}
    binding = ActivityPresentation.objects.select_for_update().filter(**lookup).first()
    if binding is None:
        binding = ActivityPresentation(created_by=actor, **lookup)
    binding.template_version = template_version
    binding.theme_version = theme_version
    binding.editorial_data = editorial_data or {}
    binding.visual_overrides = visual_overrides or {}
    binding.state = PresentationState.DRAFT
    binding.published_at = None
    binding.save()
    return binding


@transaction.atomic
def publish_activity_presentation(*, actor, presentation):
    presentation = ActivityPresentation.objects.select_for_update().select_related("activity", "template_version", "theme_version").get(pk=presentation.pk)
    ensure_activity_presentation_authority(actor, presentation.activity)
    if presentation.template_version.status != VersionStatus.PUBLISHED or presentation.theme_version.status != VersionStatus.PUBLISHED:
        raise ValidationError("Le modèle et le thème doivent être publiés.")
    presentation.state = PresentationState.PUBLISHED
    presentation.published_at = timezone.now()
    presentation.save(update_fields=["state", "published_at", "updated_at"])
    return presentation
