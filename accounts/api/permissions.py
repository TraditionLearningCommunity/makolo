from rest_framework.permissions import BasePermission


def user_has_role(user, role_code: str, legacy_flag: str | None = None) -> bool:
    """Legacy global-role compatibility only.

    Contextual Makolo authority is resolved by authorization.services.can.
    This helper remains for historical organization-less event/scanner paths and
    must not receive new business responsibilities.
    """
    if not getattr(user, "is_authenticated", False):
        return False

    if getattr(user, "is_superuser", False):
        return True

    # Existing staff accounts receive an explicit platform Mandate in the data
    # migration. A newly-created is_staff account does not get business powers
    # merely because it may enter Django admin.
    from authorization.services import has_platform_authority

    if has_platform_authority(user):
        return True

    if user.roles.filter(code=role_code, is_active=True).exists():
        return True

    if legacy_flag:
        return bool(getattr(user, legacy_flag, False))

    return False


class IsAdmin(BasePermission):
    """Technical Django staff gate for account-administration API surfaces."""

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_staff


class IsOrganizer(BasePermission):
    """Compatibility permission; new scoped endpoints must use Mandates."""

    def has_permission(self, request, view):
        return user_has_role(
            request.user,
            "organizer",
            legacy_flag="is_organizer",
        )


class IsScannerAgent(BasePermission):
    """Compatibility permission; scanner assignments are contextual authority."""

    def has_permission(self, request, view):
        return user_has_role(
            request.user,
            "scanner-agent",
            legacy_flag="is_scanner_agent",
        )


class IsSelfOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        return obj == request.user or request.user.is_staff
