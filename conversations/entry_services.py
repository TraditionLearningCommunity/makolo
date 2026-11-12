"""Durable Exchange mutations, serialized by their owning Point."""
import hashlib
import json
from datetime import timedelta
from uuid import UUID

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from .entry_models import ConversationEntryMention, ConversationEntryReaction, ConversationEntryReceipt, ConversationEntryRevision
from .point_models import ConversationPoint, PointExchangeEntry
from .point_services import _active_window, _validate_represented_space, point_response_allowed, point_visible_to
from .realtime_events import invalidate_point
from .services import can_manage_conversation, can_moderate_conversation

REACTIONS = ("👍", "❤️", "🙏", "✅", "👀", "🎉")


class ExchangeConflict(ValidationError):
    pass


def payload_hash(body, reply_to_id=None, represented_space_id=None, mentions=(), references=(), media=None):
    value = {"body": body.strip(), "reply_to_id": str(reply_to_id) if reply_to_id else None,
             "represented_space_id": str(represented_space_id) if represented_space_id else None,
             "mentions": sorted(str(value) for value in mentions), "references": sorted(references, key=lambda x: json.dumps(x, sort_keys=True))}
    if media is not None:
        value["media"] = media
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def clean_body(body):
    if not isinstance(body, str) or not body.strip() or len(body) > 5000:
        raise ValidationError({"body": "Un texte de 1 à 5 000 caractères est attendu."})
    return body.strip()


def clean_reference(value, *, required=False):
    if value is None and not required:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > 80:
        raise ValidationError({"client_reference": "Référence d'envoi obligatoire (80 caractères maximum)."})
    return value.strip()


def lock_point(point_id):
    return ConversationPoint.objects.select_for_update(of=("self",)).select_related("conversation__policy").get(pk=point_id)


def entries_for(profile, point):
    if point.kind != "exchange" or not point_visible_to(profile, point):
        raise PermissionDenied("Échange inaccessible.")
    rows = PointExchangeEntry.objects.filter(point=point)
    if not can_manage_conversation(profile, point.conversation):
        if point.response_visibility == "respondent_and_authorities":
            rows = rows.filter(author=profile)
        elif point.response_visibility != "point_viewers":
            rows = rows.none()
    return rows


def mention_ids(values):
    if not isinstance(values, (list, tuple)) or len(values) > 20:
        raise ValidationError({"mention_profile_ids": "20 mentions maximum."})
    try:
        ids = {UUID(str(value)) for value in values}
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValidationError({"mention_profile_ids": "Mention invalide."}) from exc
    return ids


def validate_mentions(actor, point, values):
    ids = mention_ids(values)
    profiles = list(get_user_model().objects.filter(pk__in=ids, is_active=True))
    if len(profiles) != len(ids) or any(
        not point_visible_to(profile, point)
        or (point.response_visibility != "point_viewers" and profile.pk != actor.pk
            and not can_manage_conversation(profile, point.conversation))
        for profile in profiles
    ):
        raise ValidationError({"mention_profile_ids": "Destinataire inaccessible dans cet échange."})
    return profiles


def touch_entry(point, entry, *, fields=()):
    point.exchange_stream_version += 1
    point.save(update_fields=["exchange_stream_version", "updated_at"])
    entry.last_change_version = point.exchange_stream_version
    entry.save(update_fields=[*fields, "last_change_version", "updated_at"])
    invalidate_point(point)


def touch_quotes(point, entry):
    # Quotes are projected snippets, so dependent messages must join the delta.
    for reply in PointExchangeEntry.objects.filter(reply_to=entry).iterator(chunk_size=500):
        touch_entry(point, reply)


def legacy_media_replay(entry, body, uploaded_media):
    if entry.origin_payload_hash or uploaded_media is None:
        return False
    file = uploaded_media["file"]
    file.seek(0)
    original_hash = hashlib.sha256(file.read()).hexdigest()
    file.seek(0)
    attachment = entry.attachments.filter(kind=uploaded_media["kind"], content_hash=original_hash).first()
    if attachment is None:
        return False
    revision = entry.revisions.order_by("to_version").first()
    original_body_hash = revision.old_content_sha256 if revision else payload_hash(entry.body)
    # This is exactly the old owner's caption-or-filename normalization.
    return original_body_hash == payload_hash(body or attachment.original_name)


@transaction.atomic
def send_entry(*, actor, point, body, reply_to=None, represented_space=None, client_reference=None,
               mention_profile_ids=(), references=(), uploaded_media=None):
    point = lock_point(point.pk)
    if point.kind != "exchange":
        raise ValidationError("Ce Point n'autorise pas la discussion libre.")
    if not point_visible_to(actor, point):
        raise PermissionDenied("Échange inaccessible.")
    media_digest = None
    if uploaded_media is not None:
        from .media_services import validate_conversation_upload, _ensure_policy
        _, _, digest = validate_conversation_upload(uploaded_media["file"], uploaded_media["kind"])
        media_digest = {"kind": uploaded_media["kind"], "sha256": digest}
    if (uploaded_media is not None or references) and (body is None or body == ""):
        body = ""
    else:
        body = clean_body(body)
    ref = clean_reference(client_reference)
    ids = mention_ids(mention_profile_ids)
    from .reference_services import validate_references
    from .entry_models import ConversationEntryReference
    references = validate_references(actor, references, check_access=False)
    digest = payload_hash(body, getattr(reply_to, "pk", None), getattr(represented_space, "pk", None), ids, references, media_digest)
    if ref:
        existing = PointExchangeEntry.objects.filter(client_reference=ref).first()
        if existing:
            same_subject = existing.point_id == point.pk and existing.author_id == actor.pk
            legacy_match = (same_subject and not ids and not references
                            and existing.reply_to_id == getattr(reply_to, "pk", None)
                            and existing.represented_space_id == getattr(represented_space, "pk", None)
                            and legacy_media_replay(existing, body, uploaded_media))
            if same_subject and (existing.origin_payload_hash == digest or legacy_match):
                return existing
            raise ExchangeConflict("Cette référence d'envoi est déjà utilisée pour un autre contenu.")
    if not point.conversation.policy.allow_free_exchange or not point_response_allowed(actor, point):
        raise PermissionDenied("Vous ne pouvez pas contribuer à cet échange.")
    _validate_represented_space(actor, represented_space)
    mentions = validate_mentions(actor, point, list(ids))
    validate_references(actor, references)
    if uploaded_media is not None:
        _ensure_policy(point, uploaded_media["kind"])
    _active_window(point)
    if reply_to and (reply_to.point_id != point.pk or not entries_for(actor, point).filter(pk=reply_to.pk, moderation_state="visible").exists()):
        raise PermissionDenied("Le message cité n'est pas accessible.")
    sequence = (point.exchange_entries.aggregate(value=Max("sequence"))["value"] or 0) + 1
    point.exchange_stream_version += 1
    point.save(update_fields=["exchange_stream_version", "updated_at"])
    try:
        with transaction.atomic():
            entry = PointExchangeEntry(
                point=point, author=actor, body=body, reply_to=reply_to, represented_space=represented_space,
                client_reference=ref, origin_payload_hash=digest, sequence=sequence,
                last_change_version=point.exchange_stream_version,
                content_kind="mixed" if body and (references or uploaded_media) else "reference" if references else "media" if uploaded_media else "text",
            )
            entry._validated_entry_content = bool(references or uploaded_media)
            entry.save()
    except IntegrityError as exc:
        raise ExchangeConflict("Cette référence d'envoi est déjà utilisée.") from exc
    ConversationEntryMention.objects.bulk_create([ConversationEntryMention(entry=entry, profile=p) for p in mentions])
    ConversationEntryReference.objects.bulk_create([
        ConversationEntryReference(entry=entry, created_by=actor, **{f"{r['kind']}_id": r["id"]}) for r in references
    ])
    from .domain_event_signals import _emit
    from domain_events.contracts import DomainEventType
    _emit(event_type=DomainEventType.CONVERSATION_ENTRY_CREATED, source_type="conversation_entry",
          source_id=entry.pk, conversation=point.conversation, suffix="created",
          payload={"conversation_id": str(point.conversation_id), "point_id": str(point.pk), "entry_id": str(entry.pk)})
    invalidate_point(point)
    if uploaded_media is not None:
        from .media_services import create_point_attachment
        create_point_attachment(actor=actor, point=point, uploaded_file=uploaded_media["file"],
                                kind=uploaded_media["kind"], exchange_entry=entry)
    return entry


def editable(actor, entry):
    return (entry.author_id == actor.pk and entry.moderation_state == "visible"
            and timezone.now() <= entry.created_at + timedelta(seconds=settings.CONVERSATIONS_REALTIME_EDIT_SECONDS))


def mutation_entry(actor, point, entry):
    current = entries_for(actor, point).filter(pk=entry.pk).first()
    if current is None:
        raise PermissionDenied("Message inaccessible.")
    return current


@transaction.atomic
def edit_entry(*, actor, entry, body, expected_edit_version, client_reference, mention_profile_ids=None):
    point = lock_point(entry.point_id)
    entry = mutation_entry(actor, point, entry)
    ref = clean_reference(client_reference, required=True)
    body = "" if body == "" and (entry.attachments.exists() or entry.references.exists()) else clean_body(body)
    ids = mention_ids(mention_profile_ids if mention_profile_ids is not None else list(entry.mentions.values_list("profile_id", flat=True)))
    digest = payload_hash(body, mentions=ids)
    prior = entry.revisions.filter(client_reference=ref).first()
    if prior:
        if prior.editor_id != actor.pk or prior.from_version != expected_edit_version or prior.new_content_sha256 != digest:
            raise ExchangeConflict("Cette référence de modification est déjà utilisée.")
        return entry
    mentions = validate_mentions(actor, point, list(ids))
    _active_window(point)
    if not point_response_allowed(actor, point) or not editable(actor, entry):
        raise PermissionDenied("Ce message ne peut plus être modifié.")
    if entry.edit_version != expected_edit_version:
        raise ExchangeConflict("Le message a changé. Rechargez-le avant de le modifier.")
    ConversationEntryRevision.objects.create(
        entry=entry, editor=actor, from_version=entry.edit_version, to_version=entry.edit_version + 1,
        old_content_sha256=payload_hash(entry.body, mentions=entry.mentions.values_list("profile_id", flat=True)),
        new_content_sha256=digest, client_reference=ref,
    )
    entry.body = body
    entry.edit_version += 1
    entry.edited_at = timezone.now()
    previous_mentions = set(entry.mentions.values_list("profile_id", flat=True))
    entry.mentions.all().delete()
    ConversationEntryMention.objects.bulk_create([ConversationEntryMention(entry=entry, profile=p) for p in mentions])
    touch_entry(point, entry, fields=["body", "edit_version", "edited_at"])
    touch_quotes(point, entry)
    if any(p.pk not in previous_mentions for p in mentions):
        from .domain_event_signals import _emit
        from domain_events.contracts import DomainEventType
        _emit(event_type=DomainEventType.CONVERSATION_ENTRY_MENTIONED, source_type="conversation_entry",
              source_id=entry.pk, conversation=point.conversation, suffix=f"mentions:{entry.edit_version}",
              payload={"conversation_id": str(point.conversation_id), "point_id": str(point.pk), "entry_id": str(entry.pk)})
    return entry


@transaction.atomic
def delete_entry(*, actor, entry):
    point = lock_point(entry.point_id)
    entry = mutation_entry(actor, point, entry)
    if entry.author_id != actor.pk and not can_moderate_conversation(actor, point.conversation):
        raise PermissionDenied("Vous ne pouvez pas supprimer ce message.")
    if entry.moderation_state == "removed":
        return entry
    _active_window(point)
    if entry.author_id == actor.pk and not point_response_allowed(actor, point):
        raise PermissionDenied("Cet échange n'accepte plus de modification.")
    entry.moderation_state, entry.removed_at, entry.removed_by = "removed", timezone.now(), actor
    touch_entry(point, entry, fields=["moderation_state", "removed_at", "removed_by"])
    touch_quotes(point, entry)
    return entry


@transaction.atomic
def react_entry(*, actor, entry, emoji, selected):
    if emoji not in REACTIONS or not isinstance(selected, bool):
        raise ValidationError("Réaction invalide.")
    point = lock_point(entry.point_id)
    entry = mutation_entry(actor, point, entry)
    if entry.moderation_state != "visible":
        raise ExchangeConflict("Ce message a été retiré.")
    _active_window(point)
    if not point_response_allowed(actor, point):
        raise PermissionDenied("Vous ne pouvez pas réagir dans cet échange.")
    # A private reply must not receive a reaction from an undiscoverable viewer.
    if point.response_visibility != "point_viewers" and actor.pk != entry.author_id:
        raise PermissionDenied("Réactions indisponibles pour cette audience.")
    if selected:
        _, changed = ConversationEntryReaction.objects.get_or_create(entry=entry, actor=actor, emoji=emoji)
    else:
        changed, _ = ConversationEntryReaction.objects.filter(entry=entry, actor=actor, emoji=emoji).delete()
    if changed:
        touch_entry(point, entry)
    return entry


@transaction.atomic
def acknowledge_entries(*, actor, point, delivered_sequence, read_sequence):
    point = lock_point(point.pk)
    rows = entries_for(actor, point)
    for value in (delivered_sequence, read_sequence):
        if type(value) is not int or value < 0 or (value and not rows.filter(sequence=value).exists()):
            raise ValidationError("Séquence de réception inaccessible.")
    if read_sequence > delivered_sequence:
        raise ValidationError("La lecture doit être précédée de la réception.")
    receipt, _ = ConversationEntryReceipt.objects.get_or_create(point=point, profile=actor)
    changed = False
    now = timezone.now()
    if delivered_sequence > receipt.delivered_sequence:
        changed = True
        receipt.delivered_sequence, receipt.delivered_at = delivered_sequence, now
    if read_sequence > receipt.read_sequence:
        changed = True
        receipt.read_sequence, receipt.read_at = read_sequence, now
    if changed:
        receipt.save()
        # Receipt changes have their own invalidation. Do not manufacture a
        # content revision for every message covered by a monotone watermark.
        from .realtime_events import invalidate_receipts
        invalidate_receipts(point)
    return receipt
