from authorization.constants import PermissionCode
from authorization.services import can


def user_can_access_operations(user) -> bool:
    """Operations is Makolo business authority, not a Django-admin side effect."""
    return can(user, PermissionCode.PLATFORM_MANAGE)
