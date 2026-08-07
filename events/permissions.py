from rest_framework.permissions import BasePermission

from accounts.api.permissions import user_has_role


def user_can_manage_events(user) -> bool:
    return user_has_role(
        user,
        "organizer",
        legacy_flag="is_organizer",
    )


def user_can_manage_event(user, event) -> bool:
    if not user.is_authenticated:
        return False
    if user.is_staff:
        return True
    return event.organizer_id == user.pk and user_can_manage_events(user)


class IsEventOrganizer(BasePermission):
    def has_permission(self, request, view):
        return user_can_manage_events(request.user)


class IsEventOwnerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return user_can_manage_event(request.user, obj)
