from __future__ import annotations

import hashlib

from .models import AchievementDefinition, AchievementGrant


def _matches(account, criteria):
    criteria = criteria or {}
    checks = {
        "lifetime_earned_gte": account.lifetime_earned,
        "lifetime_spent_gte": account.lifetime_spent,
        "balance_gte": account.points_balance,
    }
    for key, actual in checks.items():
        if key in criteria and actual < int(criteria[key]):
            return False
    return bool(criteria) and all(key in checks for key in criteria)


def grant_due_achievements(*, account, evaluation=None):
    grants = []
    for achievement in AchievementDefinition.objects.filter(is_active=True).order_by("code"):
        if not _matches(account, achievement.criteria):
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
                },
            },
        )
        if created:
            grants.append(grant)
    return tuple(grants)
