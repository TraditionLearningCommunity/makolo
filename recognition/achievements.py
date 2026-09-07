from __future__ import annotations

import hashlib

from django.db.models import Count, Q, Sum

from .models import AchievementDefinition, AchievementGrant, RecognitionAllocation


def _trajectory(account):
    allocations = RecognitionAllocation.objects.filter(account=account)
    return {
        "allocations": allocations.count(),
        "objects": allocations.values("evaluation__object_type", "evaluation__object_id").distinct().count(),
        "channels": allocations.values("evaluation__receipt__channel").distinct().count(),
        "causal_modes": allocations.values("causal_mode").distinct().count(),
        "rules": allocations.values("evaluation__rule_id").exclude(evaluation__rule_id__isnull=True).distinct().count(),
        "points_attributed": int(allocations.aggregate(total=Sum("points"))["total"] or 0),
    }


def _matches(account, criteria):
    criteria = criteria or {}
    trajectory = _trajectory(account)
    checks = {
        "lifetime_earned_gte": account.lifetime_earned,
        "lifetime_spent_gte": account.lifetime_spent,
        "balance_gte": account.points_balance,
        "allocations_gte": trajectory["allocations"],
        "distinct_objects_gte": trajectory["objects"],
        "distinct_channels_gte": trajectory["channels"],
        "distinct_causal_modes_gte": trajectory["causal_modes"],
        "distinct_rules_gte": trajectory["rules"],
        "points_attributed_gte": trajectory["points_attributed"],
    }
    if not criteria:
        return False, trajectory
    for key, expected in criteria.items():
        if key not in checks:
            return False, trajectory
        if checks[key] < int(expected):
            return False, trajectory
    return True, trajectory


def grant_due_achievements(*, account, evaluation=None):
    grants = []
    for achievement in AchievementDefinition.objects.filter(is_active=True).order_by("code"):
        matched, trajectory = _matches(account, achievement.criteria)
        if not matched:
            continue
        digest = hashlib.sha256(f"{achievement.pk}|{account.pk}".encode()).hexdigest()
        grant, created = AchievementGrant.objects.get_or_create(
            achievement=achievement,
            account=account,
            defaults={
                "evaluation": evaluation,
                "idempotency_key": f"achievement:{digest}",
                "evidence": {
                    "lifetime_earned": account.lifetime_earned,
                    "lifetime_spent": account.lifetime_spent,
                    "balance": account.points_balance,
                    "trajectory": trajectory,
                },
            },
        )
        if created:
            grants.append(grant)
    return tuple(grants)
