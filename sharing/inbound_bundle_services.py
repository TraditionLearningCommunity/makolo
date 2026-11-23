"""Sharing-owned reception of complete, private Mark intake batches.

This is staging, not a Mark action, Resource, Proof, or Requirement.
"""
import hashlib
import json
import re
from uuid import UUID

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from journeys.collaboration_services import validate_artifact_upload
from .document_services import (
    _capture_created, _normalize_url, _safe_original_name,
    create_inbound_capture,
)
from .inbound_models import (
    InboundCapture, InboundCaptureBundle, InboundCaptureSourceKind,
)

MAX_FILES = 10
MAX_FILE_BYTES = 25 * 1024 * 1024
MAX_TOTAL_BYTES = 60 * 1024 * 1024
MAX_TEXT = 20000
_AUDIO_FORMATS = {
    ".m4a": "audio/mp4", ".mp4": "audio/mp4",
    ".webm": "audio/webm", ".wav": "audio/wav",
    ".mp3": "audio/mpeg", ".aac": "audio/aac",
    ".ogg": "audio/ogg",
}
_DOCUMENT_FORMATS = {
    ".pdf": "application/pdf", ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
    ".png": "image/png",
}
_IMAGE_WEBP = {".webp": "image/webp"}


def _verified_upload(upload):
    import os
    filename = _safe_original_name(getattr(upload, "name", "document"))
    suffix = os.path.splitext(filename)[1].lower()
    mime = str(getattr(upload, "content_type", "")).split(";")[0].strip().lower()
    if mime in {"audio/x-m4a", "audio/m4a"}:
        mime = "audio/mp4"
    if mime == "audio/x-wav":
        mime = "audio/wav"
    if suffix not in {**_DOCUMENT_FORMATS, **_AUDIO_FORMATS, **_IMAGE_WEBP}:
        raise ValidationError("Ce format de fichier n'est pas accepté.")
    expected = {**_DOCUMENT_FORMATS, **_AUDIO_FORMATS, **_IMAGE_WEBP}[suffix]
    if mime != expected:
        raise ValidationError("Le type de fichier ne correspond pas à son contenu annoncé.")
    size = int(getattr(upload, "size", 0) or 0)
    if size <= 0 or size > MAX_FILE_BYTES:
        raise ValidationError("Une pièce est vide ou dépasse 25 Mo.")
    if suffix in _DOCUMENT_FORMATS:
        data, _mime, digest = validate_artifact_upload(upload)
    else:
        upload.seek(0)
        data = upload.read(MAX_FILE_BYTES + 1)
        upload.seek(0)
        if len(data) != size or len(data) > MAX_FILE_BYTES:
            raise ValidationError("La taille de la pièce est incohérente.")
        if suffix in _AUDIO_FORMATS:
            valid = (
                (mime == "audio/mp4" and len(data) >= 12 and data[4:8] == b"ftyp")
                or (mime == "audio/webm" and data.startswith(bytes.fromhex("1a45dfa3")))
                or (mime == "audio/wav" and data.startswith(b"RIFF") and data[8:12] == b"WAVE")
                or (mime == "audio/mpeg" and (data.startswith(b"ID3") or (len(data) > 1 and data[0] == 0xff and data[1] & 0xe0 == 0xe0)))
                or (mime == "audio/aac" and len(data) > 1 and data[0] == 0xff and data[1] & 0xf0 == 0xf0)
                or (mime == "audio/ogg" and data.startswith(b"OggS"))
            )
        else:
            valid = mime == "image/webp" and data.startswith(b"RIFF") and data[8:12] == b"WEBP"
        if not valid:
            raise ValidationError("Le contenu ne correspond pas au format annoncé.")
        digest = hashlib.sha256(data).hexdigest()
    return filename, mime, data, digest


def _normalize_context(context):
    if not isinstance(context, dict):
        raise ValidationError("Contexte invalide.")
    if set(context) - {"selected", "responsibility"}:
        raise ValidationError("Ce contexte n'est pas accepté.")
    result = {}
    selected = context.get("selected")
    if selected is not None:
        if not isinstance(selected, dict) or set(selected) - {"kind", "id", "family"}:
            raise ValidationError("Sélection invalide.")
        if any(not isinstance(v, str) or len(v) > 100 for v in selected.values()):
            raise ValidationError("Sélection invalide.")
        result["selected"] = selected
    responsibility = context.get("responsibility")
    if responsibility is not None:
        if not isinstance(responsibility, str) or len(responsibility) > 100:
            raise ValidationError("Responsabilité invalide.")
        result["responsibility"] = responsibility
    return result


def receive_inbound_bundle(*, actor, request_key, text="", links=None,
                           context=None, files=(), space=None):
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Authentification requise.")
    if not isinstance(request_key, str) or not re.fullmatch(r"[0-9a-fA-F-]{32,64}", request_key):
        raise ValidationError("Identifiant de demande invalide.")
    if not isinstance(text, str) or len(text) > MAX_TEXT:
        raise ValidationError("Texte trop long.")
    if not isinstance(links, list) or len(links) > 10 or any(not isinstance(link, str) for link in links):
        raise ValidationError("Liens invalides.")
    urls = list(dict.fromkeys(_normalize_url(link) for link in links))
    context = _normalize_context(context or {})
    files = list(files)
    if len(files) > MAX_FILES:
        raise ValidationError("10 pièces maximum.")
    if not text.strip() and not urls and not files:
        raise ValidationError("Ajoutez du texte ou une pièce.")
    if sum(int(getattr(file, "size", 0) or 0) for file in files) > MAX_TOTAL_BYTES:
        raise ValidationError("Les pièces dépassent la taille totale autorisée.")
    verified = [_verified_upload(file) for file in files]
    manifest = {
        "text": text, "links": urls, "context": context,
        "space": str(space.pk) if space is not None else None,
        "files": [
            {"filename": name, "mime": mime, "size": len(data), "sha256": digest}
            for name, mime, data, digest in verified
        ],
    }
    digest = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    created_files = []
    try:
        with transaction.atomic():
            # Serialize retries from the same authenticated Profile even when
            # the same request is concurrently submitted via mobile and Web.
            actor.__class__.objects.select_for_update().get(pk=actor.pk)
            existing = InboundCaptureBundle.objects.filter(
                created_by=actor, request_key=request_key
            ).first()
            if existing is not None:
                if existing.payload_digest != digest:
                    raise ValidationError("Cette demande a changé. Enregistrez-la comme nouvelle demande.")
                return existing, False
            bundle = InboundCaptureBundle.objects.create(
                created_by=actor, space=space, request_key=request_key,
                payload_digest=digest, text=text, links=urls, context=context,
            )
            if text.strip():
                bundle.captures.add(create_inbound_capture(
                    actor=actor, source_kind=InboundCaptureSourceKind.TEXT, text=text,
                ))
            for url in urls:
                bundle.captures.add(create_inbound_capture(
                    actor=actor, source_kind=InboundCaptureSourceKind.URL, source_url=url,
                ))
            for filename, mime, data, _sha in verified:
                capture = InboundCapture(
                    created_by=actor, source_kind=InboundCaptureSourceKind.FILE,
                    original_filename=filename, mime_type=mime, size=len(data),
                )
                capture.file.save("capture.bin", ContentFile(data), save=False)
                created_files.append((capture.file.storage, capture.file.name))
                capture.save()
                bundle.captures.add(_capture_created(capture))
            return bundle, True
    except Exception:
        # Storage is not transactional; never leave files that belong to a
        # rolled-back receipt.
        for storage, name in created_files:
            try:
                storage.delete(name)
            except Exception:
                pass
        raise


def bundle_receipt(bundle):
    return {
        "state": "received" if not bundle.is_expired else "expired",
        "receipt_id": str(bundle.pk),
        "received_at": bundle.received_at.isoformat(),
        "expires_at": bundle.expires_at.isoformat(),
        "actor_context": {"kind": "space", "slug": bundle.space.slug} if bundle.space_id else {"kind": "profile"},
        "capture_count": bundle.captures.count(),
        "file_count": bundle.captures.filter(source_kind=InboundCaptureSourceKind.FILE).count(),
        "message": "Demande reçue." if not bundle.is_expired else "Cette demande n'est plus disponible.",
        "action_confirmed": False,
    }
