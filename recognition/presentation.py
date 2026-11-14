"""Owner-provided public labels for real Recognition rewards.

Only validated Subscriptions features get the "feature" presentation.
A feature grant is NOT a SubscriptionPlan purchase; no invented subscription
reward, entitlement or permission may be shown.
"""
from .models import RewardKind


def reward_spend_presentation(reward):
    result = {"category": "reward", "action": "Utiliser"}
    if reward.kind != RewardKind.ENTITLEMENT:
        return result

    from subscriptions.models import FeatureDefinition
    config = reward.fulfillment or {}
    code = str(config.get("feature_code") or "").strip()
    if not code or not FeatureDefinition.objects.filter(
        code=code, is_active=True,
    ).exists():
        return result

    result = {"category": "feature", "action": "Débloquer"}
    days = config.get("duration_days")
    if type(days) is int and days > 0:
        result["duration_days"] = days
    return result
