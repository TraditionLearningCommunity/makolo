from django.db.models import Q

from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission

from .models import LoyaltyAccount, LoyaltyProgram, MembershipSubscription
from .permissions import user_can_view_loyalty_workspace


def get_programs_visible_to(user):
    queryset = LoyaltyProgram.objects.select_related("organization", "created_by")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    org_ids = space_ids_with_permission(user, PermissionCode.LOYALTY_VIEW)
    if org_ids is None:
        return queryset
    return queryset.filter(organization_id__in=org_ids)


def get_accounts_visible_to(user):
    queryset = LoyaltyAccount.objects.select_related("program__organization", "user", "current_tier")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    org_ids = space_ids_with_permission(user, PermissionCode.LOYALTY_VIEW)
    if org_ids is None:
        return queryset
    return queryset.filter(Q(user=user) | Q(program__organization_id__in=org_ids)).distinct()


def get_subscriptions_visible_to(user):
    queryset = MembershipSubscription.objects.select_related("program__organization", "plan", "user", "benefit_code")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    org_ids = space_ids_with_permission(user, PermissionCode.LOYALTY_VIEW)
    if org_ids is None:
        return queryset
    return queryset.filter(Q(user=user) | Q(program__organization_id__in=org_ids)).distinct()


def can_view_program(user, program):
    return user_can_view_loyalty_workspace(user, program.organization)
