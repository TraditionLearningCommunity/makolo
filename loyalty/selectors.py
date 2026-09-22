from django.db.models import Count, Q
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission

from .models import LoyaltyAccount, LoyaltyProgram, LoyaltyReward, LoyaltyRewardRedemption, MembershipSubscription
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


def personal_rewards_available_to(user, *, at=None):
    """Owner-backed eligibility projection for the authenticated member.

    This mirrors the non-mutating eligibility checks enforced again under lock by
    loyalty.services.redeem_reward(). It never creates an account or membership.
    """
    if not getattr(user, "is_authenticated", False):
        return []
    at = at or timezone.now()
    accounts = {
        account.program_id: account
        for account in LoyaltyAccount.objects.filter(user=user).select_related(
            "program", "program__organization"
        )
    }
    if not accounts:
        return []
    used = {
        row["reward_id"]: row["total"]
        for row in (
            LoyaltyRewardRedemption.objects.filter(
                user=user,
                status="redeemed",
                reward__program_id__in=accounts,
            )
            .values("reward_id")
            .annotate(total=Count("id"))
            .order_by()
        )
    }
    rewards = (
        LoyaltyReward.objects.filter(
            program_id__in=accounts,
            is_active=True,
            program__is_active=True,
        )
        .select_related("program", "program__organization", "promotion")
        .order_by("program__organization__name", "points_cost", "name", "id")
    )
    available = []
    for reward in rewards:
        if reward.starts_at and at < reward.starts_at:
            continue
        if reward.ends_at and at > reward.ends_at:
            continue
        if used.get(reward.pk, 0) >= reward.max_redemptions_per_member:
            continue
        account = accounts.get(reward.program_id)
        if account is None or account.points_balance < reward.points_cost:
            continue
        available.append(reward)
    return available
