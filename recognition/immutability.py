from __future__ import annotations

from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from .models import (
    AchievementDefinition,
    PolicyStatus,
    RecognitionRule,
    RecognitionSignal,
    RewardDefinition,
    RewardKind,
)


ACHIEVEMENT_PROTECTED_FIELDS = (
    "code", "name", "description", "criteria", "badge_label", "is_publicly_presentable",
)
REWARD_PROTECTED_FIELDS = (
    "code", "version", "name", "description", "kind", "points_cost", "fulfillment", "eligibility",
    "beneficiary_allowed", "acceptance_required", "stock", "valid_from", "valid_until",
)
SIGNAL_PROTECTED_FIELDS = (
    "signal_id",
    "signal_kind",
    "object_type",
    "object_id",
    "occurred_at",
    "available_at",
    "outcome_identity",
    "values",
    "contributors",
    "confidence",
    "source_ref",
)
REWARD_REQUIRED_CONFIG = {
    RewardKind.ENTITLEMENT: ("feature_code",),
    RewardKind.PROMOTION: ("promotion_id",),
    RewardKind.ACCESS: ("activity_id",),
    RewardKind.INTRODUCTION: ("match_kind",),
    RewardKind.PAYOUT: ("amount", "currency"),
    RewardKind.OTHER: ("owner_domain",),
}


def _changed(previous, instance, fields):
    return any(previous.get(field) != getattr(instance, field) for field in fields)


def _validate_reward_contract(instance):
    config = instance.fulfillment if isinstance(instance.fulfillment, dict) else {}
    missing = [key for key in REWARD_REQUIRED_CONFIG.get(instance.kind, ()) if config.get(key) in (None, "")]
    if missing:
        raise ValidationError({"fulfillment": f"Configuration Reward incomplète pour {instance.kind}: {', '.join(missing)}."})
    eligibility = instance.eligibility if isinstance(instance.eligibility, dict) else {}
    subject_types = set(eligibility.get("beneficiary_subject_types") or ["profile", "space"])
    if not subject_types or not subject_types <= {"profile", "space"}:
        raise ValidationError({"eligibility": "beneficiary_subject_types accepte uniquement profile et/ou space."})
    for name in ("max_per_owner", "max_per_beneficiary"):
        if name in eligibility:
            try:
                value = int(eligibility[name])
            except (TypeError, ValueError) as exc:
                raise ValidationError({"eligibility": f"{name} doit être un entier positif."}) from exc
            if value < 1:
                raise ValidationError({"eligibility": f"{name} doit être au moins 1."})
    if instance.kind == RewardKind.PAYOUT:
        try:
            amount = Decimal(str(config.get("amount")))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError({"fulfillment": "amount doit être un montant positif explicite."}) from exc
        currency = str(config.get("currency") or "").strip().upper()
        if not amount.is_finite() or amount <= 0 or len(currency) != 3:
            raise ValidationError({"fulfillment": "Payout exige amount positif et currency ISO explicite."})
    if instance.kind in {RewardKind.PROMOTION, RewardKind.ACCESS, RewardKind.INTRODUCTION}:
        # These v1 bridges grant a person-scoped concrete benefit. Staff can still spend Space credits for a Profile.
        allowed = set(eligibility.get("beneficiary_subject_types") or ["profile"])
        if "space" in allowed:
            raise ValidationError({"eligibility": f"La Reward {instance.kind} v1 doit limiter beneficiary_subject_types à ['profile']."})


@receiver(pre_save, sender=RecognitionRule, dispatch_uid="recognition.rule_set_immutable_after_publish")
def protect_published_policy_rule_set(sender, instance, raw=False, **kwargs):
    # Django restores serialized test databases and fixtures with raw=True.
    # That path is persistence restoration, not a business mutation, and must
    # not be blocked by runtime immutability guards.
    if raw or not instance.policy_id:
        return
    if instance.policy.status not in {PolicyStatus.DRAFT, PolicyStatus.SIMULATED}:
        raise ValidationError("Les Rules d'une Policy publiée sont immuables. Clonez la Policy dans une nouvelle version.")


@receiver(pre_save, sender=RecognitionSignal, dispatch_uid="recognition.signal_semantics_immutable")
def protect_signal_semantics(sender, instance, raw=False, **kwargs):
    if raw or not instance.pk:
        return
    previous = RecognitionSignal.objects.filter(pk=instance.pk).values(*SIGNAL_PROTECTED_FIELDS).first()
    if previous and _changed(previous, instance, SIGNAL_PROTECTED_FIELDS):
        raise ValidationError(
            "Un Signal Recognition observé est immuable. Une correction métier doit produire un nouveau fait/outcome canonique."
        )


@receiver(pre_delete, sender=RecognitionSignal, dispatch_uid="recognition.signal_no_delete")
def protect_signal_delete(sender, instance, **kwargs):
    if instance.pk:
        raise ValidationError("Un Signal Recognition observé est historique et ne peut pas être supprimé.")


@receiver(pre_save, sender=AchievementDefinition, dispatch_uid="recognition.achievement_definition_immutable_after_grant")
def protect_achievement_definition(sender, instance, raw=False, **kwargs):
    if raw:
        return
    if not instance.pk or not AchievementDefinition.objects.filter(pk=instance.pk).exists() or not instance.grants.exists():
        return
    previous = AchievementDefinition.objects.filter(pk=instance.pk).values(*ACHIEVEMENT_PROTECTED_FIELDS).first()
    if previous and _changed(previous, instance, ACHIEVEMENT_PROTECTED_FIELDS):
        raise ValidationError("Un Achievement déjà accordé ne peut plus être réinterprété. Créez une nouvelle définition pour de nouveaux critères ou une nouvelle présentation.")


@receiver(pre_delete, sender=AchievementDefinition, dispatch_uid="recognition.achievement_definition_no_delete_after_grant")
def protect_achievement_delete(sender, instance, **kwargs):
    if instance.pk and instance.grants.exists():
        raise ValidationError("Un Achievement déjà accordé est historique et ne peut pas être supprimé.")


@receiver(pre_save, sender=RewardDefinition, dispatch_uid="recognition.reward_definition_immutable_after_redemption")
def protect_reward_definition(sender, instance, raw=False, **kwargs):
    if raw:
        return
    _validate_reward_contract(instance)
    if not instance.pk or not RewardDefinition.objects.filter(pk=instance.pk).exists() or not instance.redemptions.exists():
        return
    previous = RewardDefinition.objects.filter(pk=instance.pk).values(*REWARD_PROTECTED_FIELDS).first()
    if previous and _changed(previous, instance, REWARD_PROTECTED_FIELDS):
        raise ValidationError("Une Reward déjà utilisée est historique. Clonez-la avec une nouvelle version pour modifier son économie ou son fulfillment.")


@receiver(pre_delete, sender=RewardDefinition, dispatch_uid="recognition.reward_definition_no_delete_after_redemption")
def protect_reward_delete(sender, instance, **kwargs):
    if instance.pk and instance.redemptions.exists():
        raise ValidationError("Une Reward déjà utilisée est historique et ne peut pas être supprimée.")
