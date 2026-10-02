from core.web.request_context import get_request_context

from .selectors import get_unread_notifications_count


def notifications_summary(request):
    if not getattr(request.user, "is_authenticated", False):
        return {"notifications_unread_count": 0}

    request_context = get_request_context(request)
    if not request_context.surface.needs_capability("notifications"):
        return {"notifications_unread_count": 0}

    count = request_context.memoize(
        ("notifications", "unread_count", request.user.pk),
        lambda: get_unread_notifications_count(request.user),
    )
    return {"notifications_unread_count": count}
