from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):
    """Technical Django staff gate for account-administration API surfaces."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff


class IsSelfOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj == request.user or request.user.is_staff
