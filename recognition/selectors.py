from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from .models import RecognitionAccount, RedemptionStatus, RewardDefinition


def compact_credits(value):
    value = int(value or 0)
    suffixes = (
        (10**24, "Y"), (10**21, "Z"), (10**18, "E"), (10**15, "P"),
        (10**12, "T"), (10**9, "G"), (10**6, "M"), (10**3, "k"),
    )
    for threshold, suffix in suffixes:
        if abs(value) >= threshold:
            number = value / threshold
            rendered = f"{number:.1f}".rstrip("0").rstrip(".").replace(".", ",")
            return f"{rendered}{suffix} crédits"
    return f"{value} crédits"


def account_for_profile(profile):
    return RecognitionAccount.objects.filter(profile=profile).first()


def account_for_space(space):
    return RecognitionAccount.objects.filter(space=space).first()


def _self_eligible(reward, account):
    if account is None or account.points_balance < reward.points_cost:
        return False
    eligibility = reward.eligibility or {}
    if account.lifetime_earned < int(eligibility.get("owner_lifetime_earned_gte", 0) or 0):
        return False
    subject_type = account.subject_type
    allowed = set(eligibility.get("beneficiary_subject_types") or ["profile", "space"])
    if subject_type not in allowed:
        return False
    max_owner = eligibility.get("max_per_owner")
    if max_owner is not None:
        used = reward.redemptions.exclude(status=RedemptionStatus.CANCELLED).filter(owner_account=account).count()
        if used >= int(max_owner):
            return False
    if reward.stock is not None and reward.redemptions.exclude(status=RedemptionStatus.CANCELLED).count() >= reward.stock:
        return False
    return True


def active_rewards(*, at=None, owner_account=None):
    """Return one currently usable version per Reward code, newest version wins."""
    at = at or timezone.now()
    candidates = list(
        RewardDefinition.objects.filter(is_active=True)
        .filter(Q(valid_from__isnull=True) | Q(valid_from__lte=at))
        .filter(Q(valid_until__isnull=True) | Q(valid_until__gt=at))
        .order_by("code", "-version", "id")
    )
    latest = {}
    for reward in candidates:
        latest.setdefault(reward.code, reward)
    rewards = sorted(latest.values(), key=lambda reward: (reward.points_cost, reward.name, reward.code))
    if owner_account is None:
        return rewards
    return [reward for reward in rewards if _self_eligible(reward, owner_account)]
