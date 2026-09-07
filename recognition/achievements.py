from __future__ import annotations

import hashlib

from django.db.models import Sum

from .models import AchievementDefinition, AchievementGrant, RecognitionAllocation


def _trajectory(account):
    """Derive durable trajectory from causal object-pool evidence.

    RecognitionObjectEvaluation is now one finite pool per object/window, so its
    receipt channel is the internal ``utility`` channel and ``rule`` is null.
    Achievement trajectory must read the selected business channels/rules from
    the immutable explanation instead of reviving per-rule persistence.
    """
    allocations = RecognitionAllocation.objects.filter(account=account).select_related("evaluation")
    evaluation_ids = list(allocations.values_list("evaluation_id", flat=True).distinct())
    explanations = allocations.filter(evaluation_id__in=evaluation_ids).values_list(
        "evaluation__explanation", flat=True
    ).distinct()

    channels = set()
    rules = set()
    for explanation in explanations:
        if not isinstance(explanation, dict):
            continue
        for channel in explanation.get("channels") or []:
            if channel:
                channels.add(str(channel))
        # Current object-pool explanations contain each evaluated Rule and its
        # marginal effective utility. Positive rows are a conservative fallback
        # for historical explanations that predate an explicit selected-rules list.
        selected_rules = explanation.get("selected_rules")
        if isinstance(selected_rules, list):
            rules.update(str(code) for code in selected_rules if code)
        else:
            for row in explanation.get("rule_results") or []:
                if not isinstance(row, dict) or not row.get("rule"):
                    continue
                try:
                    positive = float(row.get("effective_utility", 0)) > 0
                except (TypeError, ValueError):
                    positive = False
                if positive:
                    rules.add(str(row["rule"]))

    return {
        "allocations": allocations.count(),
        "objects": allocations.values("evaluation__object_type", "evaluation__object_id").distinct().count(),
        "channels": len(channels),
        "causal_modes": allocations.values("causal_mode").distinct().count(),
        "rules": len(rules),
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
