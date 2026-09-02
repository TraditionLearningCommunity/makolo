from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from journeys.collaboration_models import JourneyArtifactKind, JourneyArtifactSensitivity
from journeys.collaboration_services import validate_artifact_upload

from .models import PersonalAsset, PersonalAssetVersion
from .selectors import personal_asset_for_controller


def _require_controller(actor):
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentification requise.")


def _ensure_external_subject_owned(controller, subject_external_beneficiary):
    if subject_external_beneficiary is not None and subject_external_beneficiary.created_by_id != controller.pk:
        raise PermissionDenied("Ce bénéficiaire externe n’appartient pas au périmètre contrôlé par cet utilisateur.")


@transaction.atomic
def create_personal_asset(*, controller, title, subject_profile=None, subject_external_beneficiary=None, kind=JourneyArtifactKind.OTHER, sensitivity=JourneyArtifactSensitivity.NORMAL):
    _require_controller(controller)
    _ensure_external_subject_owned(controller, subject_external_beneficiary)
    asset = PersonalAsset(controller=controller, subject_profile=subject_profile, subject_external_beneficiary=subject_external_beneficiary, kind=kind, title=title, sensitivity=sensitivity)
    asset.save()
    return asset


@transaction.atomic
def create_personal_asset_version(*, actor, asset, uploaded_file, issued_at=None, expires_at=None):
    _require_controller(actor)
    locked_asset = PersonalAsset.objects.select_for_update().filter(pk=asset.pk, controller=actor).first()
    if locked_asset is None:
        raise PermissionDenied("Accès refusé à Ma Bibliothèque.")
    if locked_asset.archived_at is not None:
        raise ValidationError("Un élément archivé ne peut pas recevoir de nouvelle version.")
    data, mime_type, content_hash = validate_artifact_upload(uploaded_file)
    previous = PersonalAssetVersion.objects.select_for_update().filter(asset=locked_asset).order_by("-version").first()
    version_number = 1 if previous is None else previous.version + 1
    version = PersonalAssetVersion(asset=locked_asset, version=version_number, supersedes=previous, mime_type=mime_type, size=len(data), content_hash=content_hash, issued_at=issued_at, expires_at=expires_at, created_by=actor)
    version.file.save("asset.bin", ContentFile(data), save=False)
    try:
        version.save()
    except Exception:
        if version.file.name:
            version.file.storage.delete(version.file.name)
        raise
    return version


@transaction.atomic
def archive_personal_asset(*, actor, asset):
    _require_controller(actor)
    locked = PersonalAsset.objects.select_for_update().filter(pk=asset.pk, controller=actor).first()
    if locked is None:
        raise PermissionDenied("Accès refusé à Ma Bibliothèque.")
    if locked.archived_at is None:
        locked.archived_at = timezone.now()
        locked.save(update_fields=["archived_at", "updated_at"])
    return locked


def personal_asset_version_for_download(*, actor, version_id):
    _require_controller(actor)
    version = PersonalAssetVersion.objects.select_related("asset").filter(pk=version_id, asset__controller=actor, asset__archived_at__isnull=True).first()
    if version is None:
        raise PermissionDenied("Accès refusé à Ma Bibliothèque.")
    return version
