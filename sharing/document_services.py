from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.utils import timezone
from django.utils.text import get_valid_filename

from journeys.collaboration_models import (
    JourneyArtifact,
    JourneyArtifactKind,
    JourneyArtifactSensitivity,
    JourneyArtifactStatus,
    JourneyNoteVisibility,
    JourneyStep,
)
from journeys.collaboration_services import create_artifact, create_note, validate_artifact_upload
from journeys.models import Journey

from .inbound_models import InboundCapture, InboundCaptureSourceKind, InboundCaptureStatus


EXPORTABLE_ARTIFACT_KINDS = {
    JourneyArtifactKind.CV,
    JourneyArtifactKind.COVER_LETTER,
    JourneyArtifactKind.CERTIFICATE,
    JourneyArtifactKind.TRANSCRIPT,
    JourneyArtifactKind.RECOMMENDATION,
    JourneyArtifactKind.FORM,
}
BLOCKED_ARTIFACT_KINDS = {
    JourneyArtifactKind.IDENTITY_DOCUMENT,
    JourneyArtifactKind.PAYMENT_RECEIPT,
    JourneyArtifactKind.OTHER,
}
EXPORT_CHANNELS = {"download", "system_share"}
EXTENSIONS_BY_MIME = {
    "application/pdf": {".pdf"},
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": {".docx"},
    "application/msword": {".doc"},
    "text/plain": {".txt"},
    "image/jpeg": {".jpg", ".jpeg"},
    "image/png": {".png"},
}


@dataclass(frozen=True)
class ArtifactExportDecision:
    allowed: bool
    requires_warning: bool = False
    reason: str = ""


def can_export_journey_artifact(profile, artifact, channel="download"):
    """Allowlist-first export policy. Visibility alone never grants external export."""
    if channel not in EXPORT_CHANNELS:
        return ArtifactExportDecision(False, reason="Canal d’export non pris en charge.")
    if not getattr(profile, "is_authenticated", False):
        return ArtifactExportDecision(False, reason="Authentification requise.")
    if artifact.journey.beneficiary_id != profile.pk:
        return ArtifactExportDecision(False, reason="Seul le bénéficiaire peut exporter ce document.")
    if artifact.kind in BLOCKED_ARTIFACT_KINDS or artifact.kind not in EXPORTABLE_ARTIFACT_KINDS:
        return ArtifactExportDecision(False, reason="Ce type de document n’est pas exportable par le partage documentaire.")
    if artifact.sensitivity == JourneyArtifactSensitivity.RESTRICTED:
        return ArtifactExportDecision(False, reason="Un document restreint ne peut pas être exporté par ce canal.")
    if artifact.status == JourneyArtifactStatus.SUPERSEDED:
        return ArtifactExportDecision(False, reason="Une ancienne version remplacée n’est pas exportable.")
    if not artifact.file or not artifact.file.name:
        return ArtifactExportDecision(False, reason="Le fichier n’est pas disponible.")
    return ArtifactExportDecision(True, requires_warning=True)


def export_decision_for_artifact(*, actor, artifact_id, channel="download"):
    artifact = (
        JourneyArtifact.objects.select_related("journey", "uploaded_by", "step")
        .filter(pk=artifact_id)
        .first()
    )
    if artifact is None:
        raise PermissionDenied("Document inaccessible.")
    decision = can_export_journey_artifact(actor, artifact, channel)
    if not decision.allowed:
        raise PermissionDenied(decision.reason or "Export refusé.")
    return artifact, decision


def _normalize_url(value):
    value = (value or "").strip()
    if not value or len(value) > 2048:
        raise ValidationError("URL invalide ou trop longue.")
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError as exc:
        raise ValidationError("URL invalide.") from exc
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValidationError("Seules les URL http et https sont acceptées.")
    if parts.username or parts.password:
        raise ValidationError("Les URL contenant des identifiants ne sont pas acceptées.")
    host = parts.hostname.rstrip(".").lower()
    if host == "localhost":
        raise ValidationError("Cette adresse locale n’est pas acceptée.")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address and (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_unspecified
        or address.is_multicast
    ):
        raise ValidationError("Cette adresse réseau n’est pas acceptée.")
    netloc = host
    if port:
        if ":" in host:
            netloc = f"[{host}]:{port}"
        else:
            netloc = f"{host}:{port}"
    elif ":" in host:
        netloc = f"[{host}]"
    return urlunsplit((parts.scheme.lower(), netloc, parts.path or "", parts.query or "", ""))


def _safe_original_name(name):
    base = os.path.basename((name or "").replace("\\", "/"))
    cleaned = get_valid_filename(base)[:180]
    return cleaned or "document"


def _validate_extension(filename, mime_type):
    extension = os.path.splitext(filename)[1].lower()
    if extension not in EXTENSIONS_BY_MIME.get(mime_type, set()):
        raise ValidationError("L’extension du fichier ne correspond pas à son type MIME.")


def create_inbound_capture(*, actor, source_kind, source_url="", text="", uploaded_file=None):
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentification requise.")
    if source_kind not in InboundCaptureSourceKind.values:
        raise ValidationError("Type de Capture invalide.")
    if source_kind == InboundCaptureSourceKind.URL:
        return InboundCapture.objects.create(
            created_by=actor,
            source_kind=source_kind,
            source_url=_normalize_url(source_url),
        )
    if source_kind == InboundCaptureSourceKind.TEXT:
        body = (text or "").strip()
        if not body:
            raise ValidationError("Le texte ne peut pas être vide.")
        if len(body) > 20000:
            raise ValidationError("Le texte dépasse la taille maximale autorisée.")
        return InboundCapture.objects.create(created_by=actor, source_kind=source_kind, text=body)

    data, mime_type, _ = validate_artifact_upload(uploaded_file)
    original_name = _safe_original_name(getattr(uploaded_file, "name", "document"))
    _validate_extension(original_name, mime_type)
    capture = InboundCapture(
        created_by=actor,
        source_kind=source_kind,
        original_filename=original_name,
        mime_type=mime_type,
        size=len(data),
    )
    capture.file.save("capture.bin", ContentFile(data), save=False)
    try:
        capture.save()
    except Exception:
        if capture.file.name:
            capture.file.storage.delete(capture.file.name)
        raise
    return capture


def capture_for_actor(*, actor, capture_id, for_update=False):
    qs = InboundCapture.objects
    if for_update:
        qs = qs.select_for_update(of=("self",)).order_by()
    capture = qs.filter(pk=capture_id, created_by=actor).first()
    if capture is None:
        raise PermissionDenied("Capture inaccessible.")
    return capture


def _lock_owned_journey(actor, journey_id):
    journey = Journey.objects.select_for_update(of=("self",)).filter(pk=journey_id, beneficiary=actor).first()
    if journey is None:
        raise PermissionDenied("Démarche inaccessible.")
    return journey


def _mark_expired(capture):
    capture.status = InboundCaptureStatus.EXPIRED
    capture.save(update_fields=["status", "updated_at"])
    if capture.file and capture.file.name:
        name = capture.file.name
        storage = capture.file.storage
        transaction.on_commit(lambda: storage.delete(name))
    return capture


@transaction.atomic
def absorb_capture_into_journey(
    *,
    actor,
    capture_id,
    journey_id,
    step_id=None,
    kind=JourneyArtifactKind.OTHER,
    sensitivity=JourneyArtifactSensitivity.SENSITIVE,
    title="",
):
    capture = capture_for_actor(actor=actor, capture_id=capture_id, for_update=True)
    if capture.status == InboundCaptureStatus.ABSORBED:
        return capture.absorbed_artifact or capture.absorbed_note
    if capture.status != InboundCaptureStatus.PENDING:
        raise ValidationError("Cette Capture ne peut plus être utilisée.")
    if capture.expires_at <= timezone.now():
        _mark_expired(capture)
        raise ValidationError("Cette Capture a expiré.")

    journey = _lock_owned_journey(actor, journey_id)
    step = None
    if step_id:
        step = JourneyStep.objects.select_for_update(of=("self",)).filter(pk=step_id, journey=journey).first()
        if step is None:
            raise ValidationError("L’étape sélectionnée n’appartient pas à cette démarche.")

    if capture.source_kind == InboundCaptureSourceKind.FILE:
        if kind not in JourneyArtifactKind.values or sensitivity not in JourneyArtifactSensitivity.values:
            raise ValidationError("Type ou sensibilité de document invalide.")
        if kind == JourneyArtifactKind.IDENTITY_DOCUMENT:
            sensitivity = JourneyArtifactSensitivity.RESTRICTED
        capture.file.open("rb")
        try:
            data = capture.file.read()
        finally:
            capture.file.close()
        uploaded = SimpleUploadedFile(
            capture.original_filename or "document",
            data,
            content_type=capture.mime_type,
        )
        artifact = create_artifact(
            journey=journey,
            uploaded_file=uploaded,
            uploaded_by=actor,
            kind=kind,
            title=(title or capture.original_filename or "Document importé")[:220],
            step=step,
            sensitivity=sensitivity,
        )
        capture.absorbed_artifact = artifact
        result = artifact
    else:
        body = capture.text if capture.source_kind == InboundCaptureSourceKind.TEXT else f"Lien importé : {capture.source_url}"
        note = create_note(
            journey=journey,
            author=actor,
            body=body,
            visibility=JourneyNoteVisibility.BENEFICIARY_VISIBLE,
            step=step,
        )
        capture.absorbed_note = note
        result = note

    capture.status = InboundCaptureStatus.ABSORBED
    capture.absorbed_at = timezone.now()
    capture.source_url = ""
    capture.text = ""
    if capture.file and capture.file.name:
        staged_name = capture.file.name
        staged_storage = capture.file.storage
        capture.file = ""
        transaction.on_commit(lambda: staged_storage.delete(staged_name))
    capture.save()
    return result


@transaction.atomic
def discard_capture(*, actor, capture_id):
    capture = capture_for_actor(actor=actor, capture_id=capture_id, for_update=True)
    if capture.status == InboundCaptureStatus.ABSORBED:
        raise ValidationError("Une Capture déjà absorbée ne peut pas être ignorée.")
    if capture.status in {InboundCaptureStatus.DISCARDED, InboundCaptureStatus.EXPIRED}:
        return capture
    capture.status = InboundCaptureStatus.DISCARDED
    capture.source_url = ""
    capture.text = ""
    if capture.file and capture.file.name:
        staged_name = capture.file.name
        staged_storage = capture.file.storage
        capture.file = ""
        transaction.on_commit(lambda: staged_storage.delete(staged_name))
    capture.save()
    return capture


def expire_captures(*, limit=500):
    expired_count = 0
    ids = list(
        InboundCapture.objects.filter(status=InboundCaptureStatus.PENDING, expires_at__lte=timezone.now())
        .order_by("expires_at")
        .values_list("pk", flat=True)[:limit]
    )
    for capture_id in ids:
        with transaction.atomic():
            capture = InboundCapture.objects.select_for_update(of=("self",)).filter(
                pk=capture_id, status=InboundCaptureStatus.PENDING
            ).first()
            if capture is None or capture.expires_at > timezone.now():
                continue
            _mark_expired(capture)
            expired_count += 1
    return expired_count
