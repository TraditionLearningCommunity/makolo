from authorization.constants import PermissionCode
from authorization.services import can


def user_can_access_operations(user) -> bool:
    """Platform Operations Center remains a platform-only capability."""
    return can(user, PermissionCode.PLATFORM_MANAGE)


def user_can_view_activity_operations(user, activity) -> bool:
    if user_can_access_operations(user):
        return True
    if can(user, PermissionCode.ACTIVITY_OPERATIONS_VIEW, activity=activity):
        return True
    return bool(activity.space_id and can(user, PermissionCode.SPACE_MANAGE, activity.space))


def user_can_manage_activity_operations(user, activity) -> bool:
    if user_can_access_operations(user):
        return True
    if can(user, PermissionCode.ACTIVITY_OPERATIONS_MANAGE, activity=activity):
        return True
    return bool(activity.space_id and can(user, PermissionCode.SPACE_MANAGE, activity.space))


def user_can_manage_incident(user, incident) -> bool:
    if user_can_access_operations(user):
        return True
    if incident.activity_id:
        return user_can_manage_activity_operations(user, incident.activity)
    if incident.organization_id:
        return can(user, PermissionCode.SPACE_MANAGE, incident.organization)
    return False


def user_can_view_incident(user, incident) -> bool:
    if user_can_access_operations(user):
        return True
    if incident.activity_id:
        return user_can_view_activity_operations(user, incident.activity)
    if incident.organization_id:
        return can(user, PermissionCode.SPACE_MANAGE, incident.organization)
    return False
