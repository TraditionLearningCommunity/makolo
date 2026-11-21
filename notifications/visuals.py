"""Read-only recognition visuals for the notification inbox.

Never infer an actor from the notification recipient or an arbitrary metadata URL.
Private/unpublished Activity media must not leak into notification lists.
"""

from activities.models import ActivityStatus, ActivityVisibility


def notification_visual(notification, request=None):
    """Return a public first-party image or a deterministic semantic fallback."""
    category = notification.category or "system"
    visual = {"kind": "icon", "category": category, "image_url": None}

    activity = getattr(notification, "activity", None)
    if activity is None and notification.journey_id:
        activity = getattr(notification.journey, "activity", None)
    if activity is None:
        return visual

    if (
        activity.status != ActivityStatus.PUBLISHED
        or activity.visibility != ActivityVisibility.PUBLIC
    ):
        return visual

    try:
        event = activity.event_vertical
    except activity.__class__.event_vertical.RelatedObjectDoesNotExist:
        return visual
    if not event.cover_image:
        return visual

    url = event.cover_image.url
    if not url.startswith("/") or url.startswith("//"):
        return visual
    if request is not None:
        url = request.build_absolute_uri(url)
    return {"kind": "activity", "category": category, "image_url": url}
