from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import RecognitionRedemption, RedemptionStatus, RewardDefinition
from .services import spend_points


@transaction.atomic
def redeem_reward(*, owner_account, reward, idempotency_key, actor_profile=None, beneficiary_profile=None, beneficiary_space=None):
    if bool(beneficiary_profile) == bool(beneficiary_space):
        raise ValidationError("Choisissez exactement un bénéficiaire Profile ou Space.")
    key = (idempotency_key or "").strip()
    if not key:
        raise ValidationError("Une utilisation de crédits exige une clé d'idempotence.")
    existing = RecognitionRedemption.objects.filter(idempotency_key=key).first()
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
    spend_points(
        account=owner_account,
        points=reward.points_cost,
        idempotency_key=f"reward-spend:{key}",
        description=f"Reward : {reward.name}",
        actor_profile=actor_profile,
        metadata={"reward_id": str(reward.pk), "beneficiary_profile_id": str(getattr(beneficiary_profile, "pk", "")), "beneficiary_space_id": str(getattr(beneficiary_space, "pk", ""))},
    )
    return RecognitionRedemption.objects.create(
        owner_account=owner_account,
        reward=reward,
        beneficiary_profile=beneficiary_profile,
        beneficiary_space=beneficiary_space,
        points_cost=reward.points_cost,
        status=RedemptionStatus.REQUESTED,
        idempotency_key=key,
        fulfillment_snapshot=dict(reward.fulfillment or {}),
    )
