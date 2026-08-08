from rest_framework.permissions import BasePermission

from accounts.api.permissions import user_has_role
from organizations.models import OrganizationMembership
from organizations.permissions import (
    ACCESS_ROLES,
    EVENT_MANAGEMENT_ROLES,
    FINANCE_ROLES,
    user_has_org_role,
)


def user_can_manage_events(user) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff:
        return True
    if OrganizationMembership.objects.filter(
        user=user,
        is_active=True,
        role__in=EVENT_MANAGEMENT_ROLES,
    ).exists():
        return True
    return user_has_role(user, "organizer", legacy_flag="is_organizer")


def user_can_manage_event(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff:
        return True
    if event.organization_id and user_has_org_role(user, event.organization, EVENT_MANAGEMENT_ROLES):
        return True
    return event.organizer_id == user.pk and user_has_role(
        user, "organizer", legacy_flag="is_organizer"
    )


def user_can_manage_event_finance(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff:
        return True
    if event.organization_id:
        return user_has_org_role(user, event.organization, FINANCE_ROLES)
    return user_can_manage_event(user, event)


def user_can_manage_event_access(user, event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff:
        return True
    if event.organization_id:
        return user_has_org_role(user, event.organization, ACCESS_ROLES)
    return user_can_manage_event(user, event)


class IsEventOrganizer(BasePermission):
    def has_permission(self, request, view):
        return user_can_manage_events(request.user)


class IsEventOwnerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        return user_can_manage_event(request.user, obj)
