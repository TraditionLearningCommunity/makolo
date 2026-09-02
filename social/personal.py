from dataclasses import dataclass

from groups.models import GroupMembership, GroupMembershipStatus
from journeys.models import Journey, JourneyStatus
from loyalty.models import LoyaltyAccount, LoyaltyRewardRedemption
from trust.models import Proof, ProofStatus

from goals.models import PersonalGoal, PersonalGoalStatus
from .models import Contribution, ContributionStatus


@dataclass(frozen=True)
class PersonalStats:
    journeys_completed: int
    activities_completed: int
    groups_active: int
    contributions_published: int
    proofs_active: int
    goals_completed: int


def personal_stats(profile):
    fulfilled = Journey.objects.filter(beneficiary=profile, status=JourneyStatus.FULFILLED)
    return PersonalStats(
        journeys_completed=fulfilled.count(),
        activities_completed=fulfilled.values("activity_id").distinct().count(),
        groups_active=GroupMembership.objects.filter(profile=profile, status=GroupMembershipStatus.ACTIVE).count(),
        contributions_published=Contribution.objects.filter(author_profile=profile, status=ContributionStatus.PUBLISHED).count(),
        proofs_active=Proof.objects.filter(subject_profile=profile, status=ProofStatus.ACTIVE).count(),
        goals_completed=PersonalGoal.objects.filter(profile=profile, status=PersonalGoalStatus.COMPLETED).count(),
    )


def personal_history_extensions(profile, *, limit_each=5):
    """Private owner-only projections; no Timeline persistence or public exposure."""
    return {
        "goals": PersonalGoal.objects.filter(profile=profile, status=PersonalGoalStatus.COMPLETED).order_by("-completed_at")[:limit_each],
        "contributions": Contribution.objects.filter(author_profile=profile).select_related("activity", "group").order_by("-created_at")[:limit_each],
        "proofs": Proof.objects.filter(subject_profile=profile, status=ProofStatus.ACTIVE).select_related("journey__activity").order_by("-issued_at")[:limit_each],
        "loyalty_accounts": LoyaltyAccount.objects.filter(user=profile).select_related("program__organization", "current_tier")[:limit_each],
        "rewards": LoyaltyRewardRedemption.objects.filter(user=profile).select_related("reward", "account__program__organization").order_by("-redeemed_at")[:limit_each],
    }
