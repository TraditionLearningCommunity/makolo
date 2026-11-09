"""Atomic, owner-backed publishing of media in a structured Conversation Point.

A Point, its Poll choices, their private media and captions keep the canonical
owners. This is a composition service, never another media/answer domain.
"""
from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from .composing import publish_composed_point
from .media_models import ConversationAttachmentKind
from .media_services import (
    KIND_POLICY_FIELD, _validate_kind_mime, create_point_attachment,
    validate_conversation_upload,
)
from .point_models import ConversationPointKind


def response_media_label(point, response):
    """Human-readable answer only for viewers already authorized for its media."""
    if response is None:
        return ""
    value = response.value
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if point.response_mode in {"single_choice", "multiple_choice"}:
        known = {str(option.pk): option.label for option in point.options.all()}
        values = value if isinstance(value, list) else [value]
        return ", ".join(known.get(str(item), "Choix") for item in values)
    if isinstance(value, (str, int, float)):
        return str(value)[:500]
    return ""


@transaction.atomic
def publish_semantic_point_with_media(
    *, actor, conversation, kind, title, body, client_reference, media_items,
    options=None, multiple_choice=False, audience_id=None, represented_space=None,
):
    """Publish one complete, ordered Point with media bound to their context.

    Media entries have scope='point' or 'option', option_index for choice media,
    kind, caption and an uploaded_file. A replay must match the original bytes
    and media placement. No partial Point is returned on upload failure.
    """
    if not isinstance(media_items, list) or not 1 <= len(media_items) <= 24:
        raise ValidationError({"media": "Prévoyez entre 1 et 24 médias."})
    if kind not in {
        ConversationPointKind.INFORMATION, ConversationPointKind.QUESTION,
        ConversationPointKind.REQUEST, ConversationPointKind.CONFIRMATION,
        ConversationPointKind.POLL, ConversationPointKind.EXCHANGE,
    }:
        raise ValidationError({"kind": "Type de Point inconnu."})
    policy = getattr(conversation, "policy", None)
    validated = []
    for item in media_items:
        scope = item.get("scope")
        index = item.get("option_index")
        file = item.get("uploaded_file")
        media_kind = item.get("kind")
        caption = item.get("caption", "")
        if scope not in {"point", "option"} or file is None:
            raise ValidationError({"media": "Emplacement de média invalide."})
        if scope == "option" and (
            kind != ConversationPointKind.POLL
            or not isinstance(index, int) or isinstance(index, bool)
            or not isinstance(options, list) or not 0 <= index < len(options)
        ):
            raise ValidationError({"media": "Choix de sondage invalide."})
        if media_kind not in ConversationAttachmentKind.values:
            raise ValidationError({"media": "Type de média inconnu."})
        if policy is None or not getattr(policy, KIND_POLICY_FIELD[media_kind], False):
            raise PermissionDenied("Ce média n'est pas autorisé dans cette Conversation.")
        if not isinstance(caption, str) or len(caption.strip()) > 5000:
            raise ValidationError({"media": "Légende trop longue."})
        # Validate the real bytes, not a client-supplied extension or MIME.
        _, mime, digest = validate_conversation_upload(file, media_kind)
        _validate_kind_mime(media_kind, mime)
        validated.append({
            "scope": scope, "index": index, "file": file,
            "kind": media_kind, "caption": caption.strip(), "digest": digest,
        })
    point = publish_composed_point(
        actor=actor, conversation=conversation, kind=kind, title=title,
        body=body, options=options, multiple_choice=multiple_choice,
        audience_id=audience_id, represented_space=represented_space,
        client_reference=client_reference,
    )
    choices = list(point.options.order_by("position", "pk"))
    created = []
    try:
        # Existing idempotent publication may be replayed only as-is.
        existing = list(point.attachments.filter(
            response__isnull=True, exchange_entry__isnull=True,
        ).order_by("created_at", "pk"))
        if existing:
            if len(existing) != len(validated):
                raise ValidationError("La composition des médias a changé.")
            for media, attachment in zip(validated, existing):
                option_id = choices[media["index"]].pk if media["scope"] == "option" else None
                if (
                    attachment.option_id != option_id
                    or attachment.kind != media["kind"]
                    or attachment.caption != media["caption"]
                    or attachment.content_hash != media["digest"]
                ):
                    raise ValidationError("Ces médias diffèrent de la publication initiale.")
            return point, existing
        for media in validated:
            option = choices[media["index"]] if media["scope"] == "option" else None
            attachment = create_point_attachment(
                actor=actor, point=point, uploaded_file=media["file"],
                kind=media["kind"], option=option, caption=media["caption"],
            )
            created.append(attachment)
    except Exception:
        # Database rollback does not roll back private object storage.
        for attachment in created:
            if attachment.file.name:
                attachment.file.storage.delete(attachment.file.name)
        raise
    return point, created
