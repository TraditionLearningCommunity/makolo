from __future__ import annotations

from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from subscriptions.models import FeatureDefinition
from subscriptions.runtime_services import create_entitlement_grant

from .models import RecognitionRedemption, RedemptionStatus, RewardDefinition, RewardKind
from .services import refund_spend, spend_points


def _beneficiary_key(*, profile=None, space=None):
    if bool(profile) == bool(space):
        raise ValidationError("Choisissez exactement un bénéficiaire Profile ou Space.")
    return ("profile", profile.pk) if profile is not None else ("space", space.pk)


def _check_eligibility(*, owner_account, reward, beneficiary_profile=None, beneficiary_space=None):
    eligibility = reward.eligibility or {}
    beneficiary_type, beneficiary_id = _beneficiary_key(profile=beneficiary_profile, space=beneficiary_space)
    allowed_subjects = set(eligibility.get("beneficiary_subject_types") or ["profile", "space"])
    if beneficiary_type not in allowed_subjects:
        raise ValidationError("Ce bénéficiaire n'est pas éligible à cette Reward.")
    min_lifetime = int(eligibility.get("owner_lifetime_earned_gte", 0) or 0)
    if owner_account.lifetime_earned < min_lifetime:
        raise ValidationError("Le compte propriétaire n'est pas encore éligible à cette Reward.")
    max_owner = eligibility.get("max_per_owner")
    if max_owner is not None:
        used = reward.redemptions.exclude(status=RedemptionStatus.CANCELLED).filter(owner_account=owner_account).count()
        if used >= int(max_owner):
            raise ValidationError("La limite d'utilisation de cette Reward pour ce compte est atteinte.")
    max_beneficiary = eligibility.get("max_per_beneficiary")
    if max_beneficiary is not None:
        query = {f"beneficiary_{beneficiary_type}_id": beneficiary_id}
        used = reward.redemptions.exclude(status=RedemptionStatus.CANCELLED).filter(**query).count()
        if used >= int(max_beneficiary):
            raise ValidationError("La limite de cette Reward pour ce bénéficiaire est atteinte.")


def _fulfill_entitlement(redemption, *, actor_profile=None):
    config = redemption.fulfillment_snapshot or {}
    feature_code = str(config.get("feature_code") or "").strip()
    if not feature_code:
        raise ValidationError("La Reward Entitlement doit déclarer feature_code.")
    feature = FeatureDefinition.objects.filter(code=feature_code, is_active=True).first()
    if feature is None:
        raise ValidationError("La Feature configurée pour cette Reward n'existe pas ou est inactive.")
    value = config.get("value", True)
    duration_days = config.get("duration_days")
    valid_until = None
    if duration_days is not None:
        duration_days = int(duration_days)
        if duration_days < 1:
            raise ValidationError("duration_days doit être positif.")
        valid_until = timezone.now() + timedelta(days=duration_days)
    kwargs = {
        "feature": feature,
        "value": value,
        "reason": f"Recognition reward {redemption.reward.code}:v{redemption.reward.version}",
        "granted_by": actor_profile,
        "valid_until": valid_until,
    }
    if redemption.beneficiary_profile_id:
        kwargs["profile"] = redemption.beneficiary_profile
    else:
        kwargs["space"] = redemption.beneficiary_space
    grant = create_entitlement_grant(**kwargs)
    snapshot = dict(redemption.fulfillment_snapshot or {})
    snapshot["fulfilled_domain"] = "subscriptions"
    snapshot["entitlement_grant_id"] = str(grant.pk)
    redemption.fulfillment_snapshot = snapshot
    redemption.status = RedemptionStatus.FULFILLED
    redemption.fulfilled_at = timezone.now()
    redemption.save(update_fields=["fulfillment_snapshot", "status", "fulfilled_at"])
    return redemption


def fulfill_redemption(redemption, *, actor_profile=None):
    """Delegate a Recognition benefit to its owning domain when v1 has a stable bridge."""
    if redemption.status == RedemptionStatus.FULFILLED:
        return redemption
    if redemption.status == RedemptionStatus.CANCELLED:
        raise ValidationError("Une utilisation annulée ne peut pas être réalisée.")
    snapshot = redemption.fulfillment_snapshot or {}
    if snapshot.get("consent_state") == "pending":
        raise ValidationError("Le bénéficiaire doit accepter cette Reward avant réalisation.")
    if redemption.reward.kind == RewardKind.ENTITLEMENT:
        return _fulfill_entitlement(redemption, actor_profile=actor_profile)
    return redemption


@transaction.atomic
def redeem_reward(*, owner_account, reward, idempotency_key, actor_profile=None, beneficiary_profile=None, beneficiary_space=None):
    _beneficiary_key(profile=beneficiary_profile, space=beneficiary_space)
    key = (idempotency_key or "").strip()
    if not key:
        raise ValidationError("Une utilisation de crédits exige une clé d'idempotence.")
    existing = RecognitionRedemption.objects.filter(idempotency_key=key).select_related("reward").first()
    if existing:
        return existing

    reward = RewardDefinition.objects.select_for_update().get(pk=reward.pk)
    now = timezone.now()
    if not reward.is_active or (reward.valid_from and now < reward.valid_from) or (reward.valid_until and now >= reward.valid_until):
        raise ValidationError("Cette Reward n'est pas disponible maintenant.")
    if reward.stock is not None and reward.redemptions.exclude(status=RedemptionStatus.CANCELLED).count() >= reward.stock:
        raise ValidationError("Cette Reward n'est plus disponible.")

    owner_is_beneficiary = (
        (owner_account.profile_id and beneficiary_profile and owner_account.profile_id == beneficiary_profile.pk)
        or (owner_account.space_id and beneficiary_space and owner_account.space_id == beneficiary_space.pk)
    )
    if not owner_is_beneficiary and not reward.beneficiary_allowed:
        raise ValidationError("Cette Reward ne peut pas être utilisée pour un autre bénéficiaire.")
    _check_eligibility(
        owner_account=owner_account,
        reward=reward,
        beneficiary_profile=beneficiary_profile,
        beneficiary_space=beneficiary_space,
    )

    spend_points(
        account=owner_account,
        points=reward.points_cost,
        idempotency_key=f"reward-spend:{key}",
        description=f"Reward : {reward.name}",
        actor_profile=actor_profile,
        metadata={
            "reward_id": str(reward.pk),
            "beneficiary_profile_id": str(getattr(beneficiary_profile, "pk", "")),
            "beneficiary_space_id": str(getattr(beneficiary_space, "pk", "")),
        },
    )
    snapshot = dict(reward.fulfillment or {})
    snapshot["reward_code"] = reward.code
    snapshot["reward_version"] = reward.version
    snapshot["consent_state"] = "pending" if (reward.acceptance_required and not owner_is_beneficiary) else "not_required"
    redemption = RecognitionRedemption.objects.create(
        owner_account=owner_account,
        reward=reward,
        beneficiary_profile=beneficiary_profile,
        beneficiary_space=beneficiary_space,
        points_cost=reward.points_cost,
        status=RedemptionStatus.REQUESTED,
        idempotency_key=key,
        fulfillment_snapshot=snapshot,
    )
    if snapshot["consent_state"] != "pending":
        return fulfill_redemption(redemption, actor_profile=actor_profile)
    return redemption


def _validate_decision_subject(redemption, *, beneficiary_profile=None, beneficiary_space=None):
    if redemption.beneficiary_profile_id:
        if beneficiary_profile is None or beneficiary_profile.pk != redemption.beneficiary_profile_id or beneficiary_space is not None:
            raise ValidationError("Seul le Profile bénéficiaire peut décider pour cette Reward.")
        return beneficiary_profile
    if redemption.beneficiary_space_id:
        if beneficiary_space is None or beneficiary_space.pk != redemption.beneficiary_space_id or beneficiary_profile is not None:
            raise ValidationError("Seul l'Espace bénéficiaire, via une autorité explicite, peut décider pour cette Reward.")
        return beneficiary_space
    raise ValidationError("Cette Reward n'a pas de bénéficiaire valide.")


@transaction.atomic
def accept_redemption(*, redemption, beneficiary_profile=None, beneficiary_space=None, actor_profile=None):
    redemption = (
        RecognitionRedemption.objects.select_for_update(of=("self",))
        .select_related("reward", "beneficiary_profile", "beneficiary_space")
        .get(pk=redemption.pk)
    )
    snapshot = dict(redemption.fulfillment_snapshot or {})
    if snapshot.get("consent_state") != "pending":
        return redemption
    _validate_decision_subject(
        redemption,
        beneficiary_profile=beneficiary_profile,
        beneficiary_space=beneficiary_space,
    )
    snapshot["consent_state"] = "accepted"
    snapshot["consent_at"] = timezone.now().isoformat()
    snapshot["consent_actor_profile_id"] = str(getattr(actor_profile, "pk", ""))
    redemption.fulfillment_snapshot = snapshot
    redemption.save(update_fields=["fulfillment_snapshot"])
    return fulfill_redemption(redemption, actor_profile=actor_profile or beneficiary_profile)


@transaction.atomic
def decline_redemption(*, redemption, beneficiary_profile=None, beneficiary_space=None, actor_profile=None):
    redemption = (
        RecognitionRedemption.objects.select_for_update(of=("self",))
        .select_related("reward", "owner_account", "beneficiary_profile", "beneficiary_space")
        .get(pk=redemption.pk)
    )
    snapshot = dict(redemption.fulfillment_snapshot or {})
    if snapshot.get("consent_state") != "pending":
        raise ValidationError("Cette Reward n'attend pas de décision du bénéficiaire.")
    _validate_decision_subject(
        redemption,
        beneficiary_profile=beneficiary_profile,
        beneficiary_space=beneficiary_space,
    )
    refund_spend(
        account=redemption.owner_account,
        points=redemption.points_cost,
        idempotency_key=f"reward-refund:{redemption.idempotency_key}",
        description=f"Restitution Reward refusée : {redemption.reward.name}",
        actor_profile=actor_profile or beneficiary_profile,
        metadata={"redemption_id": str(redemption.pk)},
    )
    snapshot["consent_state"] = "declined"
    snapshot["consent_at"] = timezone.now().isoformat()
    snapshot["consent_actor_profile_id"] = str(getattr(actor_profile, "pk", ""))
    redemption.fulfillment_snapshot = snapshot
    redemption.status = RedemptionStatus.CANCELLED
    redemption.save(update_fields=["fulfillment_snapshot", "status"])
    return redemption
