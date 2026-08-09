from django.db.models import Q

from .models import LoyaltyAccount, LoyaltyProgram, MembershipSubscription
from .permissions import user_can_view_loyalty_workspace


def get_programs_visible_to(user):
    queryset = LoyaltyProgram.objects.select_related("organization", "created_by")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_staff:
        return queryset
    return queryset.filter(
        organization__memberships__user=user,
        organization__memberships__is_active=True,
        organization__memberships__role__in=["owner", "admin", "marketing", "finance"],
    ).distinct()


def get_accounts_visible_to(user):
    queryset = LoyaltyAccount.objects.select_related("program__organization", "user", "current_tier")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_staff:
        return queryset
    workspace_orgs = get_programs_visible_to(user).values_list("organization_id", flat=True)
    return queryset.filter(Q(user=user) | Q(program__organization_id__in=workspace_orgs)).distinct()


def get_subscriptions_visible_to(user):
    queryset = MembershipSubscription.objects.select_related("program__organization", "plan", "user", "benefit_code")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    if user.is_staff:
        return queryset
    workspace_orgs = get_programs_visible_to(user).values_list("organization_id", flat=True)
    return queryset.filter(Q(user=user) | Q(program__organization_id__in=workspace_orgs)).distinct()


def can_view_program(user, program):
    return bool(user.is_staff or user_can_view_loyalty_workspace(user, program.organization))
