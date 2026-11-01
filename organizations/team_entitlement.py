"""Enforcement at the Organizations owner boundary, using Subscription truth.

Call this under an Organization row lock before admitting a distinct active
Profile. Existing membership, removal, and non-expanding operations survive
quota reductions. A missing commercial quota is not a fabricated zero limit.
"""
from django.core.exceptions import ValidationError

from subscriptions.entitlements import resolve_entitlement
from subscriptions.selectors import get_subscription_for_subject

from .models import TeamMembership, TeamMembershipStatus


def require_team_member_capacity(space, user):
    already_counted = TeamMembership.objects.filter(
        team__organization=space,
        team__is_active=True,
        status=TeamMembershipStatus.ACTIVE,
        user=user,
    ).exists()
    if already_counted:
        return

    if get_subscription_for_subject(space) is None:
        raise ValidationError({
            "subscription": "Cet Espace ne dispose pas de Subscription canonique."
        })
    entitlement = resolve_entitlement(space, "team.members")
    # The technical default BASE deliberately does not set a commercial quota.
    if entitlement.effective_value is None:
        return
    if not entitlement.allowed:
        raise ValidationError({
            "subscription": "La capacité de membres actifs de cet Espace ne permet pas une nouvelle admission."
        })
