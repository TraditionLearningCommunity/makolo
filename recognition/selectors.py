from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from .models import RecognitionAccount, RewardDefinition


def compact_credits(value):
    value = int(value or 0)
    suffixes = ((10**12, "T"), (10**9, "G"), (10**6, "M"), (10**3, "k"))
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


def active_rewards(*, at=None):
    at = at or timezone.now()
    return RewardDefinition.objects.filter(is_active=True).filter(Q(valid_from__isnull=True) | Q(valid_from__lte=at)).filter(Q(valid_until__isnull=True) | Q(valid_until__gt=at)).order_by("points_cost", "name")
