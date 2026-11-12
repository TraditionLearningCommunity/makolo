"""One ACL-filtered message representation for Web and mobile."""
from django.core.exceptions import PermissionDenied, ValidationError
from .entry_services import REACTIONS, editable, entries_for
from .media_services import can_download_attachment
from .point_services import _active_window, point_response_allowed, point_visible_to
from .rich_services import serialize_attachment
from .services import can_moderate_conversation


def entry_ack(entry, *, profile=None):
    entry.point.refresh_from_db(fields=["exchange_stream_version"])
    result = {"kind": "exchange", "id": str(entry.pk), "entry_id": str(entry.pk),
            "point_id": str(entry.point_id), "status": "confirmed", "sequence": entry.sequence,
            "stream_version": entry.point.exchange_stream_version, "client_reference": entry.client_reference,
            "created_at": entry.created_at, "edit_version": entry.edit_version,
            "removed": entry.moderation_state != "visible"}
    if profile is not None and entry.author_id != profile.pk:
        result.pop("client_reference", None)
    return result


def project_entry(profile, entry, *, point=None):
    point = point or entry.point
    entry.point = point
    removed = entry.moderation_state != "visible"
    own = entry.author_id == profile.pk
    active = False
    try:
        _active_window(point)
        active = point_response_allowed(profile, point)
    except ValidationError:
        pass
    quote = None
    if not removed and entry.reply_to_id:
        target = entries_for(profile, point).filter(pk=entry.reply_to_id).select_related("author").first()
        if target:
            quote = {"id": str(target.pk), "sequence": target.sequence,
                     "removed": target.moderation_state != "visible",
                     "body": target.body[:160] if target.moderation_state == "visible" else "",
                     "author": target.author.get_full_name() or target.author.username}
    reactions = []
    if not removed:
        rows = list(entry.reactions.all())
        reactions = [{"emoji": emoji, "count": sum(r.emoji == emoji for r in rows),
                      "selected": any(r.emoji == emoji and r.actor_id == profile.pk for r in rows)}
                     for emoji in REACTIONS if any(r.emoji == emoji for r in rows)]
    result = {
        "id": str(entry.pk), "entry_id": str(entry.pk), "point_id": str(entry.point_id),
        "own": own, "body": "" if removed else entry.body, "removed": removed,
        "sequence": entry.sequence, "last_change_version": entry.last_change_version,
        "edit_version": entry.edit_version, "edited_at": entry.edited_at,
        "created_at": entry.created_at, "content_kind": entry.content_kind,
        "author": {"id": str(entry.author_id), "label": entry.author.get_full_name() or entry.author.username},
        "represented_space": {"id": str(entry.represented_space_id), "label": entry.represented_space.name} if entry.represented_space_id else None,
        "reply_to": quote, "reactions": reactions,
        "mentions": [{"id": str(m.profile_id), "label": m.profile.get_full_name() or m.profile.username}
                     for m in entry.mentions.select_related("profile") if point_visible_to(m.profile, point)] if not removed else [],
        "attachments": [serialize_attachment(a) for a in entry.attachments.all() if can_download_attachment(profile, a)] if not removed else [],
        "capabilities": {"reply": active and not removed, "edit": active and editable(profile, entry),
                         "delete": active and not removed and (own or can_moderate_conversation(profile, point.conversation)),
                         "react": active and not removed and (point.response_visibility == "point_viewers" or own)},
    }
    from .reference_services import project_reference
    result["references"] = []
    if not removed:
        for reference in entry.references.all():
            try:
                result["references"].append(project_reference(profile, reference))
            except PermissionDenied:
                result["references"].append({"id": str(reference.pk), "available": False})
    if own:
        result["client_reference"] = entry.client_reference
        # Counts only; collective audiences must never expose device/Profile IDs.
        cache = getattr(point, "_receipt_projection", {})
        if profile.pk not in cache:
            from .services import can_manage_conversation
            cache[profile.pk] = [r for r in point.entry_receipts.exclude(profile=profile).select_related("profile")
                                 if point_visible_to(r.profile, point) and (
                                     point.response_visibility == "point_viewers" or can_manage_conversation(r.profile, point.conversation))]
            point._receipt_projection = cache
        authorized = cache[profile.pk]
        result["delivery"] = {
            "delivered_count": sum(r.delivered_sequence >= entry.sequence for r in authorized),
            "read_count": sum(r.read_sequence >= entry.sequence for r in authorized),
        }
    return result


def projected_rows(rows):
    return rows.select_related("author", "represented_space", "point__conversation__policy").prefetch_related("attachments", "reactions")
