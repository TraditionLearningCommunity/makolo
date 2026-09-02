from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone

from journeys.collaboration_models import JourneyArtifactKind, JourneyArtifactSensitivity
from journeys.collaboration_services import artifact_for_download, create_artifact, validate_artifact_upload

from .models import PersonalAsset, PersonalAssetUse, PersonalAssetVersion


SENSITIVITY_RANK = {
    JourneyArtifactSensitivity.NORMAL: 0,
    JourneyArtifactSensitivity.SENSITIVE: 1,
    JourneyArtifactSensitivity.RESTRICTED: 2,
}


def _require_controller(actor):
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentification requise.")


def _ensure_external_subject_owned(controller, subject_external_beneficiary):
    if subject_external_beneficiary is not None and subject_external_beneficiary.created_by_id != controller.pk:
        raise PermissionDenied("Ce bénéficiaire externe n’appartient pas au périmètre contrôlé par cet utilisateur.")


def _more_sensitive(left, right):
    return left if SENSITIVITY_RANK[left] >= SENSITIVITY_RANK[right] else right


@transaction.atomic
def create_personal_asset(*, controller, title, subject_profile=None, subject_external_beneficiary=None, kind=JourneyArtifactKind.OTHER, sensitivity=JourneyArtifactSensitivity.NORMAL):
    _require_controller(controller)
    _ensure_external_subject_owned(controller, subject_external_beneficiary)
    asset = PersonalAsset(controller=controller, subject_profile=subject_profile, subject_external_beneficiary=subject_external_beneficiary, kind=kind, title=title, sensitivity=sensitivity)
    asset.save()
    return asset


@transaction.atomic
def create_personal_asset_version(*, actor, asset, uploaded_file, issued_at=None, expires_at=None, source_journey_artifact=None):
    _require_controller(actor)
    locked_asset = PersonalAsset.objects.select_for_update().filter(pk=asset.pk, controller=actor).first()
    if locked_asset is None:
        raise PermissionDenied("Accès refusé à Ma Bibliothèque.")
    if locked_asset.archived_at is not None:
        raise ValidationError("Un élément archivé ne peut pas recevoir de nouvelle version.")
    data, mime_type, content_hash = validate_artifact_upload(uploaded_file)
    previous = PersonalAssetVersion.objects.select_for_update().filter(asset=locked_asset).order_by("-version").first()
    version_number = 1 if previous is None else previous.version + 1
    version = PersonalAssetVersion(
        asset=locked_asset,
        version=version_number,
        supersedes=previous,
        mime_type=mime_type,
        size=len(data),
        content_hash=content_hash,
        issued_at=issued_at,
        expires_at=expires_at,
        source_journey_artifact=source_journey_artifact,
        created_by=actor,
    )
    version.file.save("asset.bin", ContentFile(data), save=False)
    try:
        version.save()
    except Exception:
        if version.file.name:
            version.file.storage.delete(version.file.name)
        raise
    return version


@transaction.atomic
def use_personal_asset_version_in_journey(*, actor, personal_asset_version, journey, step=None, title=None, kind=None):
    _require_controller(actor)
    source = (
        PersonalAssetVersion.objects.select_related("asset")
        .filter(pk=personal_asset_version.pk, asset__controller=actor, asset__archived_at__isnull=True)
        .first()
    )
    if source is None:
        raise PermissionDenied("Accès refusé à cet élément de Ma Bibliothèque.")
    with source.file.open("rb") as stream:
        data = stream.read()
    upload = SimpleUploadedFile("library-snapshot.bin", data, content_type=source.mime_type)
    artifact = create_artifact(
        journey=journey,
        step=step,
        uploaded_file=upload,
        uploaded_by=actor,
        kind=kind or source.asset.kind,
        title=(title or source.asset.title).strip(),
        sensitivity=source.asset.sensitivity,
    )
    if artifact.content_hash != source.content_hash or artifact.size != source.size:
        raise ValidationError("Le snapshot Journey ne correspond pas exactement à la version sélectionnée.")
    PersonalAssetUse.objects.create(asset_version=source, journey_artifact=artifact, used_by=actor)
    return artifact


@transaction.atomic
def save_journey_artifact_to_library(*, actor, journey_artifact, title=None, kind=None, asset=None, subject_profile=None, subject_external_beneficiary=None, issued_at=None, expires_at=None):
    _require_controller(actor)
    source = artifact_for_download(actor=actor, artifact_id=journey_artifact.pk)
    if asset is None:
        if subject_profile is None and subject_external_beneficiary is None:
            subject_profile = actor
        target = create_personal_asset(
            controller=actor,
            title=(title or source.title).strip(),
            subject_profile=subject_profile,
            subject_external_beneficiary=subject_external_beneficiary,
            kind=kind or source.kind,
            sensitivity=source.sensitivity,
        )
    else:
        target = PersonalAsset.objects.select_for_update().filter(pk=asset.pk, controller=actor, archived_at__isnull=True).first()
        if target is None:
            raise PermissionDenied("Accès refusé à cet élément de Ma Bibliothèque.")
        conservative = _more_sensitive(target.sensitivity, source.sensitivity)
        if conservative != target.sensitivity:
            target.sensitivity = conservative
            target.save(update_fields=["sensitivity", "updated_at"])
    with source.file.open("rb") as stream:
        data = stream.read()
    upload = SimpleUploadedFile("journey-snapshot.bin", data, content_type=source.mime_type)
    version = create_personal_asset_version(
        actor=actor,
        asset=target,
        uploaded_file=upload,
        issued_at=issued_at,
        expires_at=expires_at,
        source_journey_artifact=source,
    )
    if version.content_hash != source.content_hash or version.size != source.size:
        raise ValidationError("La copie vers Ma Bibliothèque ne correspond pas exactement à l’Artifact source.")
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
