from django.contrib.auth import get_user_model


User = get_user_model()


def get_users():
    return (
        User.objects
        .select_related("profile", "notification_preferences")
        .order_by("-created_at")
    )


def get_user_by_id(user_id):
    return (
        User.objects
        .select_related("profile", "notification_preferences")
        .filter(id=user_id)
        .first()
    )
