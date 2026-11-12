"""Inbox facts derived from the same Entry visibility and read watermarks."""
from .entry_services import entries_for
from .point_services import point_visible_to


def exchange_list_summary(profile, conversation):
    unread, latest = 0, None
    for point in conversation.points.filter(kind="exchange").select_related("conversation__policy"):
        if not point_visible_to(profile, point):
            continue
        rows = entries_for(profile, point)
        receipt = point.entry_receipts.filter(profile=profile).first()
        watermark = receipt.read_sequence if receipt else 0
        unread += rows.filter(moderation_state="visible", sequence__gt=watermark).exclude(author=profile).count()
        entry = rows.select_related("author").order_by("-created_at", "-pk").first()
        if entry and (latest is None or (entry.created_at, entry.pk) > (latest.created_at, latest.pk)):
            latest = entry
    state = conversation.user_states.filter(profile=profile).first()
    return {"unread_count": unread,
            "last_message": ({"id": str(latest.pk), "point_id": str(latest.point_id),
                              "body": latest.body[:160] if latest.moderation_state == "visible" else "",
                              "removed": latest.moderation_state != "visible", "created_at": latest.created_at,
                              "own": latest.author_id == profile.pk} if latest else None),
            "personal_state": {"pinned": bool(state and state.pinned_at), "muted": bool(state and state.muted_at)},
            "group_discussion": conversation.context.kind != "direct"}
