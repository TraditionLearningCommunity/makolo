from .models import Notification


def notifications_summary(request):
    if not getattr(request.user, "is_authenticated", False):
        return {"notifications_unread_count": 0}
    return {
        "notifications_unread_count": Notification.objects.filter(
            recipient=request.user,
            read_at__isnull=True,
        ).count()
    }
