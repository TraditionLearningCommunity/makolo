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


def reward_self_actionable(reward, owner_account):
    """Confirm a self-benefit has a compatible owner, not just enough credits.

    Other-beneficiary rewards remain supported by Recognition's owner API but
    are not presented as one-tap self spending in Appuis.
    """
    if owner_account is None:
        return False
    if reward.kind == RewardKind.PAYOUT:
        return False
    if reward.kind in {RewardKind.ACCESS, RewardKind.PROMOTION}:
        if owner_account.space_id:
            return False
    if reward.kind == RewardKind.OTHER:
        return bool(str((reward.fulfillment or {}).get("owner_domain") or "").strip())
    if reward.kind != RewardKind.ENTITLEMENT:
        return True
    from subscriptions.models import FeatureDefinition
    config = reward.fulfillment or {}
    code = str(config.get("feature_code") or "").strip()
    if not code:
        return False
    feature = FeatureDefinition.objects.filter(
        code=code, is_active=True,
    ).first()
    if feature is None:
        return False
    return (
        bool(feature.supports_profile) if owner_account.profile_id
        else bool(feature.supports_space)
    )
