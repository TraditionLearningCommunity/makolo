from __future__ import annotations

from pathlib import Path
import hashlib

from django.conf import settings

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction

from journeys.collaboration_services import validate_artifact_upload

from .media_models import ConversationAttachmentKind, ConversationPointAttachment
from .point_models import ConversationExchangeModerationState, ConversationResponseVisibility
from .point_services import point_response_allowed, point_visible_to
from .services import can_manage_conversation, can_publish_in_conversation


KIND_POLICY_FIELD = {
    ConversationAttachmentKind.FILE: "allow_documents",
    ConversationAttachmentKind.IMAGE: "allow_images",
    ConversationAttachmentKind.AUDIO: "allow_voice",
    ConversationAttachmentKind.VOICE: "allow_voice",
    ConversationAttachmentKind.VIDEO: "allow_video",
}


def _validate_kind_mime(kind, mime_type):
    if kind == ConversationAttachmentKind.IMAGE and not mime_type.startswith("image/"):
        raise ValidationError("Une pièce jointe Image doit contenir une image.")
    if kind in {ConversationAttachmentKind.AUDIO, ConversationAttachmentKind.VOICE} and not mime_type.startswith("audio/"):
        raise ValidationError("Une pièce jointe audio/vocale doit contenir un fichier audio.")
    if kind == ConversationAttachmentKind.VIDEO and not mime_type.startswith("video/"):
        raise ValidationError("Une pièce jointe Vidéo doit contenir une vidéo.")


def validate_conversation_upload(uploaded_file, kind):
    """Conversation audio is not a JourneyArtifact and needs its own validation.

    The Journey validator remains the owner of document/image validation.
    No uploaded MIME declaration alone is trusted for recorded media.
    """
    if kind not in {ConversationAttachmentKind.AUDIO, ConversationAttachmentKind.VOICE, ConversationAttachmentKind.VIDEO}:
        return validate_artifact_upload(uploaded_file)
    if uploaded_file is None:
        raise ValidationError("Un fichier est obligatoire.")
    bound = int(getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", 12 * 1024 * 1024))
    size = int(getattr(uploaded_file, "size", 0) or 0)
    if size <= 0 or size > bound:
        raise ValidationError("Taille de média non prise en charge.")
    mime = (getattr(uploaded_file, "content_type", "") or "").split(";", 1)[0].strip().lower()
    signatures = {
        "audio/webm": lambda b: b.startswith(b"\x1a\x45\xdf\xa3") and b"A_OPUS" in b[:8192],
        "audio/ogg": lambda b: b.startswith(b"OggS") and (b"OpusHead" in b[:4096] or b"vorbis" in b[:4096]),
        "audio/mp4": lambda b: len(b) >= 12 and b[4:8] == b"ftyp",
        "audio/x-m4a": lambda b: len(b) >= 12 and b[4:8] == b"ftyp",
        "audio/wav": lambda b: b.startswith(b"RIFF") and b[8:12] == b"WAVE",
        "audio/mpeg": lambda b: b.startswith(b"ID3") or (len(b) > 2 and b[0] == 255 and b[1] & 0xE0 == 0xE0),
        "video/mp4": lambda b: len(b) >= 12 and b[4:8] == b"ftyp",
        "video/webm": lambda b: b.startswith(b"\x1a\x45\xdf\xa3"),
    }
    allowed = (
        {"video/mp4", "video/webm"} if kind == ConversationAttachmentKind.VIDEO
        else {"audio/webm", "audio/ogg", "audio/mp4", "audio/x-m4a", "audio/wav", "audio/mpeg"}
    )
    uploaded_file.seek(0)
    data = uploaded_file.read(bound + 1)
    uploaded_file.seek(0)
    if mime not in allowed or len(data) != size or not signatures[mime](data):
        raise ValidationError("Format ou signature du média non pris en charge.")
    return data, mime, hashlib.sha256(data).hexdigest()


def _ensure_policy(point, kind):
    policy = getattr(point.conversation, "policy", None)
    if policy is None or not getattr(policy, KIND_POLICY_FIELD[kind]):
        raise ValidationError("Ce type de média n’est pas autorisé dans cette Conversation.")


def _ensure_upload_authority(*, actor, point, response=None, exchange_entry=None, option=None):
    if option is not None:
        if option.point_id != point.pk or point.kind != "poll":
            raise PermissionDenied("Le choix n'appartient pas à ce Sondage.")
        if point.published_by_id != getattr(actor, "pk", None):
            raise PermissionDenied("Seul l'auteur peut publier les médias de ce choix.")
        if point.responses.exists():
            raise PermissionDenied("Les médias des choix ne changent plus après une réponse.")
        if not can_publish_in_conversation(actor, point.conversation):
            raise PermissionDenied("Publication non autorisée.")
        return
    if response is not None:
        if response.point_id != point.pk or response.actor_id != getattr(actor, "pk", None):
            raise PermissionDenied("Vous ne pouvez pas joindre un fichier à cette réponse.")
        if not point_response_allowed(actor, point):
            raise PermissionDenied("Vous ne pouvez plus répondre à ce Point.")
        return
    if exchange_entry is not None:
        if exchange_entry.point_id != point.pk or exchange_entry.author_id != getattr(actor, "pk", None):
            raise PermissionDenied("Vous ne pouvez pas joindre un fichier à cet échange.")
        if not point_visible_to(actor, point):
            raise PermissionDenied("Ce Point n’est pas accessible.")
        return
    if not can_publish_in_conversation(actor, point.conversation):
        raise PermissionDenied("Vous ne pouvez pas publier de pièce jointe sur ce Point.")


@transaction.atomic
def create_point_attachment(
    *, actor, point, uploaded_file, kind=ConversationAttachmentKind.FILE,
    response=None, exchange_entry=None, option=None, caption="",
):
    if sum(value is not None for value in (response, exchange_entry, option)) > 1:
        raise ValidationError("Une pièce jointe doit avoir un seul contexte.")
    _ensure_upload_authority(actor=actor, point=point, response=response,
                             exchange_entry=exchange_entry, option=option)
    _ensure_policy(point, kind)
    data, mime_type, content_hash = validate_conversation_upload(uploaded_file, kind)
    _validate_kind_mime(kind, mime_type)
    attachment = ConversationPointAttachment(
        point=point,
        response=response,
        exchange_entry=exchange_entry,
        option=option,
        caption=(caption or "").strip(),
        kind=kind,
        original_name=Path(getattr(uploaded_file, "name", "fichier")).name[:255],
        mime_type=mime_type,
        size=len(data),
        content_hash=content_hash,
        uploaded_by=actor,
    )
    attachment.file.save("payload.bin", ContentFile(data), save=False)
    try:
        attachment.save()
    except Exception:
        if attachment.file.name:
            attachment.file.storage.delete(attachment.file.name)
        raise
    return attachment


def can_download_attachment(
    actor, attachment: ConversationPointAttachment, *,
    visibility_cache=None, audience_cache=None, history_cache=None,
    manager_cache=None,
) -> bool:
    point = attachment.point
    if not point_visible_to(
        actor, point, visibility_cache=visibility_cache,
        audience_cache=audience_cache, history_cache=history_cache,
    ):
        return False

    def _can_manage():
        if manager_cache is None:
            return can_manage_conversation(actor, point.conversation)
        key = (getattr(actor, "pk", None), point.conversation_id)
        if key not in manager_cache:
            manager_cache[key] = can_manage_conversation(actor, point.conversation)
        return manager_cache[key]

    if attachment.response_id:
        response = attachment.response
        if _can_manage():
            return True
        if response.actor_id == getattr(actor, "pk", None):
            return True
        if point.response_visibility == ConversationResponseVisibility.POINT_VIEWERS:
            return True
        # Aggregate results never reveal the underlying respondent attachment.
        return False
    if attachment.exchange_entry_id:
        entry = attachment.exchange_entry
        manager = _can_manage()
        if entry.moderation_state != ConversationExchangeModerationState.VISIBLE:
            return bool(manager or entry.author_id == getattr(actor, "pk", None))
        if manager:
            return True
        if point.response_visibility == ConversationResponseVisibility.POINT_VIEWERS:
            return True
        if point.response_visibility == ConversationResponseVisibility.RESPONDENT_AND_AUTHORITIES:
            return entry.author_id == getattr(actor, "pk", None)
        return False
    return True


def attachment_for_download(*, actor, attachment_id):
    attachment = (
        ConversationPointAttachment.objects.select_related(
            "point__conversation__context",
            "point__visibility_audience",
            "response",
            "exchange_entry",
            "uploaded_by",
        )
        .filter(pk=attachment_id)
        .first()
    )
    if attachment is None or not can_download_attachment(actor, attachment):
        raise PermissionDenied("Pièce jointe inaccessible.")
    return attachment
