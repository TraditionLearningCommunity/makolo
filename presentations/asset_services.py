from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction

from authorization.constants import PermissionCode
from authorization.services import can
from journeys.collaboration_services import validate_artifact_upload

from .asset_models import PresentationAsset
from .enums import Provenance

IMAGE_MIME_TYPES = {"image/jpeg", "image/png"}


@transaction.atomic
def create_presentation_asset(*, actor, uploaded_file, activity=None, owner_space=None):
    if activity is not None and not can(actor, PermissionCode.ACTIVITY_MANAGE, activity=activity):
        raise PermissionDenied("Vous ne pouvez pas ajouter d’image à cette Activity.")
    if owner_space is not None and activity is not None and activity.space_id != owner_space.pk:
        raise ValidationError("L’asset Espace doit correspondre à l’Espace de l’Activity.")
    data, mime_type, checksum = validate_artifact_upload(uploaded_file)
    if mime_type not in IMAGE_MIME_TYPES:
        raise ValidationError("MPS accepte uniquement des images JPEG ou PNG validées.")
    provenance = Provenance.SPACE if owner_space is not None else Provenance.USER
    asset = PresentationAsset(
        provenance=provenance,
        owner_space=owner_space,
        owner_profile=None if owner_space is not None else actor,
        uploaded_by=actor,
        mime_type=mime_type,
        size=len(data),
        checksum=checksum,
    )
    extension = ".png" if mime_type == "image/png" else ".jpg"
    asset.file.save(f"asset{extension}", ContentFile(data), save=False)
    try:
        asset.save()
    except Exception:
        if asset.file.name:
            asset.file.storage.delete(asset.file.name)
        raise
    return asset
