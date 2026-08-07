from rest_framework.permissions import BasePermission


class IsAdmin(BasePermission):

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated
            and request.user.is_staff
        )


class IsOrganizer(BasePermission):

    def has_permission(self, request, view):

        if not request.user.is_authenticated:
            return False

        return (
            request.user.is_organizer
            or request.user.is_staff
        )


class IsScannerAgent(BasePermission):

    def has_permission(self, request, view):

        if not request.user.is_authenticated:
            return False

        return (
            request.user.is_scanner_agent
            or request.user.is_staff
        )


class IsSelfOrAdmin(BasePermission):

    def has_object_permission(
        self,
        request,
        view,
        obj
    ):

        return (
            obj == request.user
            or request.user.is_staff
        )