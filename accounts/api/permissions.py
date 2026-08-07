from rest_framework.permissions import BasePermission


def user_has_role(user, role_code: str, legacy_flag: str | None = None) -> bool:
    """Return whether a user has an active Makolo role.

    Role assignments are the preferred source for business authorization.
    Legacy boolean flags remain a compatibility fallback until they are removed
    by a dedicated data migration.
    """
    if not user.is_authenticated:
        return False

    if user.is_staff:
        return True

    if user.roles.filter(code=role_code, is_active=True).exists():
        return True

    if legacy_flag:
        return bool(getattr(user, legacy_flag, False))

    return False


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff


class IsOrganizer(BasePermission):
    def has_permission(self, request, view):
        return user_has_role(
            request.user,
            "organizer",
            legacy_flag="is_organizer",
        )


class IsScannerAgent(BasePermission):
    def has_permission(self, request, view):
        return user_has_role(
            request.user,
            "scanner-agent",
            legacy_flag="is_scanner_agent",
        )


class IsSelfOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj == request.user or request.user.is_staff
