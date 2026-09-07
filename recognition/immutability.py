from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver

from .models import AchievementDefinition, RewardDefinition


ACHIEVEMENT_PROTECTED_FIELDS = (
    "code",
    "name",
    "description",
    "criteria",
    "badge_label",
    "is_publicly_presentable",
)
REWARD_PROTECTED_FIELDS = (
    "code",
    "version",
    "name",
    "description",
    "kind",
    "points_cost",
    "fulfillment",
    "eligibility",
    "beneficiary_allowed",
    "acceptance_required",
    "stock",
    "valid_from",
    "valid_until",
)


def _changed(previous, instance, fields):
    return any(previous.get(field) != getattr(instance, field) for field in fields)


@receiver(pre_save, sender=AchievementDefinition, dispatch_uid="recognition.achievement_definition_immutable_after_grant")
def protect_achievement_definition(sender, instance, **kwargs):
    if not instance.pk or not AchievementDefinition.objects.filter(pk=instance.pk).exists():
        return
    if not instance.grants.exists():
        return
    previous = AchievementDefinition.objects.filter(pk=instance.pk).values(*ACHIEVEMENT_PROTECTED_FIELDS).first()
    if previous and _changed(previous, instance, ACHIEVEMENT_PROTECTED_FIELDS):
        raise ValidationError(
            "Un Achievement déjà accordé ne peut plus être réinterprété. "
            "Créez une nouvelle définition pour de nouveaux critères ou une nouvelle présentation."
        )


@receiver(pre_delete, sender=AchievementDefinition, dispatch_uid="recognition.achievement_definition_no_delete_after_grant")
def protect_achievement_delete(sender, instance, **kwargs):
    if instance.pk and instance.grants.exists():
        raise ValidationError("Un Achievement déjà accordé est historique et ne peut pas être supprimé.")


@receiver(pre_save, sender=RewardDefinition, dispatch_uid="recognition.reward_definition_immutable_after_redemption")
def protect_reward_definition(sender, instance, **kwargs):
    if not instance.pk or not RewardDefinition.objects.filter(pk=instance.pk).exists():
        return
    if not instance.redemptions.exists():
        return
    previous = RewardDefinition.objects.filter(pk=instance.pk).values(*REWARD_PROTECTED_FIELDS).first()
    if previous and _changed(previous, instance, REWARD_PROTECTED_FIELDS):
        raise ValidationError(
            "Une Reward déjà utilisée est historique. Clonez-la avec une nouvelle version pour modifier son économie ou son fulfillment."
        )


@receiver(pre_delete, sender=RewardDefinition, dispatch_uid="recognition.reward_definition_no_delete_after_redemption")
def protect_reward_delete(sender, instance, **kwargs):
    if instance.pk and instance.redemptions.exists():
        raise ValidationError("Une Reward déjà utilisée est historique et ne peut pas être supprimée.")
