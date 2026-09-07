from __future__ import annotations

from pathlib import Path

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


def _ensure_policy(point, kind):
    policy = getattr(point.conversation, "policy", None)
    if policy is None or not getattr(policy, KIND_POLICY_FIELD[kind]):
        raise ValidationError("Ce type de média n’est pas autorisé dans cette Conversation.")


def _ensure_upload_authority(*, actor, point, response=None, exchange_entry=None):
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
def create_point_attachment(*, actor, point, uploaded_file, kind=ConversationAttachmentKind.FILE, response=None, exchange_entry=None):
    _ensure_upload_authority(actor=actor, point=point, response=response, exchange_entry=exchange_entry)
    _ensure_policy(point, kind)
    data, mime_type, content_hash = validate_artifact_upload(uploaded_file)
    _validate_kind_mime(kind, mime_type)
    attachment = ConversationPointAttachment(
        point=point,
        response=response,
        exchange_entry=exchange_entry,
        kind=kind,
        original_name=Path(getattr(uploaded_file, "name", "fichier")).name[:255],
        mime_type=mime_type,
        size=len(data),
        content_hash=content_hash,
        uploaded_by=actor,
    )
    attachment.file.save("payload.bin", ContentFile(data), save=False)
    attachment.save()
    return attachment


def can_download_attachment(actor, attachment: ConversationPointAttachment) -> bool:
    point = attachment.point
    if not point_visible_to(actor, point):
        return False
    if attachment.response_id:
        response = attachment.response
        if can_manage_conversation(actor, point.conversation):
            return True
        if response.actor_id == getattr(actor, "pk", None):
            return True
        if point.response_visibility == ConversationResponseVisibility.POINT_VIEWERS:
            return True
        # Aggregate results never reveal the underlying respondent attachment.
        return False
    if attachment.exchange_entry_id:
        entry = attachment.exchange_entry
        if entry.moderation_state == ConversationExchangeModerationState.VISIBLE:
            return True
        return bool(entry.author_id == getattr(actor, "pk", None) or can_manage_conversation(actor, point.conversation))
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
