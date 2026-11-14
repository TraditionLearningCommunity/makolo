"""Institutional document authority, immutable storage and explicit reuse."""
import mimetypes
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from journeys.collaboration_models import JourneyArtifactKind, JourneyArtifactSensitivity
from journeys.models import TERMINAL_JOURNEY_STATUSES
from journeys.collaboration_services import (
    SAFE_MIME_TYPES, create_artifact, ensure_case_access, validate_artifact_upload,
)

from .models import (
    SpaceDocument, SpaceDocumentUse, SpaceDocumentVersion,
    SpaceDocumentVisibility,
)


def can_manage_documents(actor, space):
    return bool(
        getattr(actor, "is_authenticated", False)
        and has_direct_space_permission(actor, space, PermissionCode.SPACE_MANAGE)
    )


def can_read_document(actor, document):
    if not getattr(actor, "is_authenticated", False):
        return False
    if can_manage_documents(actor, document.space):
        return True
    return (
        document.visibility == SpaceDocumentVisibility.INTERNAL
        and has_direct_space_permission(actor, document.space, PermissionCode.SPACE_VIEW)
    )


def visible_documents(*, actor, space):
    """Scoped queryset; membership or Activity scope alone never authorizes."""
    if not getattr(actor, "is_authenticated", False):
        return SpaceDocument.objects.none()
    if can_manage_documents(actor, space):
        return SpaceDocument.objects.filter(space=space, archived_at__isnull=True)
    if has_direct_space_permission(actor, space, PermissionCode.SPACE_VIEW):
        return SpaceDocument.objects.filter(
            space=space, archived_at__isnull=True,
            visibility=SpaceDocumentVisibility.INTERNAL,
        )
    return SpaceDocument.objects.none()


def _require_manage(actor, space):
    if not can_manage_documents(actor, space):
        raise PermissionDenied("Vous ne pouvez pas gérer les documents de cet Espace.")


def _require_read(actor, document):
    if not can_read_document(actor, document):
        raise PermissionDenied("Document indisponible dans ce contexte.")


def _validated_upload(file):
    if file is None:
        return validate_artifact_upload(file)
    # Mobile multipart clients may send application/octet-stream.
    # A filename is only a MIME hint: shared signature validation remains
    # mandatory and rejects disguised or executable contents.
    if getattr(file, "content_type", "") == "application/octet-stream":
        guessed, _ = mimetypes.guess_type(getattr(file, "name", ""))
        if guessed in SAFE_MIME_TYPES:
            file.content_type = guessed
    return validate_artifact_upload(file)


@transaction.atomic
def create_document(
    *, actor, space, title, uploaded_file, kind=JourneyArtifactKind.OTHER,
    visibility=SpaceDocumentVisibility.RESTRICTED, issued_at=None, expires_at=None,
):
    _require_manage(actor, space)
    if kind not in JourneyArtifactKind.values:
        raise ValidationError({"kind": "Type de document non reconnu."})
    if visibility not in SpaceDocumentVisibility.values:
        raise ValidationError({"visibility": "Visibilité non reconnue."})
    # Validate before creating a durable object; no empty database records.
    data, mime_type, digest = _validated_upload(uploaded_file)
    with transaction.atomic():
        document = SpaceDocument.objects.create(
            space=space, created_by=actor, title=title,
            kind=kind, visibility=visibility,
        )
        version = _save_version(
            actor=actor, document=document, data=data, mime_type=mime_type,
            digest=digest, number=1, previous=None,
            issued_at=issued_at, expires_at=expires_at,
        )
    return document, version


def _save_version(*, actor, document, data, mime_type, digest, number, previous, issued_at, expires_at):
    version = SpaceDocumentVersion(
        document=document, version=number, supersedes=previous,
        mime_type=mime_type, size=len(data), content_hash=digest,
        issued_at=issued_at, expires_at=expires_at, created_by=actor,
    )
    version.file.save("document.bin", ContentFile(data), save=False)
    try:
        version.save()
    except Exception:
        if version.file.name:
            version.file.storage.delete(version.file.name)
        raise
    return version


@transaction.atomic
def add_document_version(
    *, actor, document, uploaded_file, issued_at=None, expires_at=None,
):
    _require_manage(actor, document.space)
    data, mime_type, digest = _validated_upload(uploaded_file)
    locked = SpaceDocument.objects.select_for_update().get(pk=document.pk)
    _require_manage(actor, locked.space)
    if locked.archived_at is not None:
        raise ValidationError("Ce document est archivé.")
    previous = locked.versions.order_by("-version").first()
    return _save_version(
        actor=actor, document=locked, data=data, mime_type=mime_type,
        digest=digest, number=previous.version + 1 if previous else 1,
        previous=previous, issued_at=issued_at, expires_at=expires_at,
    )


@transaction.atomic
def update_document(*, actor, document, title=None, visibility=None):
    locked = SpaceDocument.objects.select_for_update().get(pk=document.pk)
    _require_manage(actor, locked.space)
    if locked.archived_at is not None:
        raise ValidationError("Ce document est archivé.")
    if title is not None:
        locked.title = title
    if visibility is not None:
        if visibility not in SpaceDocumentVisibility.values:
            raise ValidationError({"visibility": "Visibilité non reconnue."})
        locked.visibility = visibility
    locked.save()
    return locked


@transaction.atomic
def archive_document(*, actor, document):
    locked = SpaceDocument.objects.select_for_update().get(pk=document.pk)
    _require_manage(actor, locked.space)
    if locked.archived_at is None:
        locked.archived_at = timezone.now()
        locked.archived_by = actor
        locked.save(update_fields=["archived_at", "archived_by", "updated_at"])
    return locked


def version_for_download(*, actor, space, version_id):
    version = (
        SpaceDocumentVersion.objects.select_related("document", "document__space")
        .filter(pk=version_id, document__space=space, document__archived_at__isnull=True)
        .first()
    )
    if version is None:
        raise PermissionDenied("Ce document n'est plus disponible.")
    _require_read(actor, version.document)
    return version


@transaction.atomic
def use_document_in_journey(
    *, actor, document_version, journey, step=None,
):
    """Create an independent JourneyArtifact, never auto-satisfy a Requirement."""
    document = (
        SpaceDocument.objects.select_for_update()
        .filter(pk=document_version.document_id, archived_at__isnull=True)
        .first()
    )
    if document is None:
        raise PermissionDenied("Document indisponible.")
    source = (
        SpaceDocumentVersion.objects.select_related("document", "document__space")
        .filter(pk=document_version.pk, document=document)
        .first()
    )
    if source is None:
        raise PermissionDenied("Document indisponible.")
    # The document lock closes the archive/change-of-visibility race.
    _require_read(actor, document)
    if journey.status in TERMINAL_JOURNEY_STATUSES:
        raise ValidationError("Cette démarche est terminée.")
    if journey.activity.space_id != document.space_id:
        raise PermissionDenied("La démarche n'appartient pas à cet Espace.")
    # A Journey-specific assignment and Activity permission remain mandatory.
    ensure_case_access(
        actor, journey, write=True,
        restricted=document.visibility == SpaceDocumentVisibility.RESTRICTED,
    )
    if source.expires_at and source.expires_at < timezone.localdate():
        raise ValidationError("Cette version est expirée.")
    with source.file.open("rb") as handle:
        data = handle.read()
    upload = SimpleUploadedFile(
        "document.bin", data, content_type=source.mime_type,
    )
    artifact = create_artifact(
        journey=journey, step=step, kind=document.kind, title=document.title,
        uploaded_file=upload, uploaded_by=actor,
        sensitivity=(
            JourneyArtifactSensitivity.RESTRICTED
            if document.visibility == SpaceDocumentVisibility.RESTRICTED
            else JourneyArtifactSensitivity.NORMAL
        ),
    )
    SpaceDocumentUse.objects.create(
        document_version=source, journey_artifact=artifact, used_by=actor,
    )
    return artifact
