from core.web.request_context import get_request_context

from .selectors import has_unread_notifications


def notifications_summary(request):
    if not getattr(request.user, "is_authenticated", False):
        return {"notifications_has_unread": False}

    request_context = get_request_context(request)
    if not request_context.surface.needs_capability("notifications"):
        return {"notifications_has_unread": False}

    has_unread = request_context.memoize(
        ("notifications", "has_unread", request.user.pk),
        lambda: has_unread_notifications(request.user),
    )
    return {"notifications_has_unread": has_unread}
