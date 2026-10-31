"""Domain-owned operations; no Discovery or client dependency."""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import can

from .media_models import PresentationMediaState, PresentationMediaUse


def _require_manage(actor, activity):
    if not getattr(actor, "is_authenticated", False) or not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity):
        raise PermissionDenied("Gestion des médias de cette Activity non autorisée.")


def _require_asset_use(actor, asset, activity):
    """Activity authority never implicitly grants rights to another owner's assets."""
    if asset.uploaded_by_id == getattr(actor, "pk", None):
        return
    if asset.owner_profile_id and asset.owner_profile_id == getattr(actor, "pk", None):
        return
    if asset.owner_space_id and activity.space_id == asset.owner_space_id and can(
        actor, PermissionCode.SPACE_MANAGE, space=activity.space
    ):
        return
    raise PermissionDenied("Utilisation de cet asset non autorisée.")


@transaction.atomic
def associate_presentation_media(*, actor, activity, asset, purpose, occurrence=None, position=0, alt_text):
    _require_manage(actor, activity)
    _require_asset_use(actor, asset, activity)
    if occurrence is not None and occurrence.activity_id != activity.pk:
        raise ValidationError({"occurrence": "Occurrence étrangère à l’Activity."})
    use = PresentationMediaUse(
        activity=activity, occurrence=occurrence, asset=asset, purpose=purpose,
        position=position, alt_text=alt_text, created_by=actor,
    )
    use.save()
    return use


@transaction.atomic
def publish_presentation_media(*, actor, media_use):
    use = PresentationMediaUse.objects.select_for_update().select_related("activity", "asset", "occurrence").get(pk=media_use.pk)
    _require_manage(actor, use.activity)
    _require_asset_use(actor, use.asset, use.activity)
    if use.state != PresentationMediaState.DRAFT:
        raise ValidationError("Seul un usage brouillon peut être publié.")
    stored_file = use.asset.private_file if use.asset.private_file else use.asset.file
    if not stored_file:
        raise ValidationError("L’asset doit posséder un fichier validé.")
    # Missing octets are an operational failure, not a new persistent status.
    if not stored_file.storage.exists(stored_file.name):
        raise ValidationError("Le fichier de l’asset est indisponible.")
    use.state = PresentationMediaState.PUBLISHED
    use.published_at = timezone.now()
    use._allow_state_transition = True
    use.save(update_fields=["state", "published_at", "updated_at"])
    return use


@transaction.atomic
def retire_presentation_media(*, actor, media_use):
    use = PresentationMediaUse.objects.select_for_update().select_related("activity").get(pk=media_use.pk)
    _require_manage(actor, use.activity)
    if use.state != PresentationMediaState.PUBLISHED:
        raise ValidationError("Seul un usage publié peut être retiré.")
    use.state = PresentationMediaState.RETIRED
    use._allow_state_transition = True
    use.save(update_fields=["state", "updated_at"])
    return use


@transaction.atomic
def reorder_presentation_media(*, actor, media_use, position):
    use = PresentationMediaUse.objects.select_for_update().select_related("activity").get(pk=media_use.pk)
    _require_manage(actor, use.activity)
    use.position = position
    use.save(update_fields=["position", "updated_at"])
    return use


@transaction.atomic
def replace_presentation_media(*, actor, media_use, asset, alt_text=None):
    """Retire published use and create draft replacement; never silently republish."""
    old = PresentationMediaUse.objects.select_for_update().select_related("activity").get(pk=media_use.pk)
    _require_manage(actor, old.activity)
    if old.state == PresentationMediaState.PUBLISHED:
        old.state = PresentationMediaState.RETIRED
        old._allow_state_transition = True
        old.save(update_fields=["state", "updated_at"])
    elif old.state != PresentationMediaState.RETIRED:
        # Draft replacement does not need a historical published object.
        old.delete()
    return associate_presentation_media(
        actor=actor, activity=old.activity, occurrence=old.occurrence,
        asset=asset, purpose=old.purpose, position=old.position,
        alt_text=alt_text if alt_text is not None else old.alt_text,
    )
