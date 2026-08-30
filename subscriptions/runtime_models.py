from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .contracts import (
    PlanVersionStatus,
    SubscriptionItemStatus,
    SubscriptionPlanType,
    SubscriptionStatus,
    SubscriptionSubjectType,
)
from .models import FeatureDefinition, PlanVersion, SubscriptionPlan


class Subscription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        null=True,
        blank=True,
    )
    space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="subscriptions",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=16, choices=SubscriptionStatus.choices, default=SubscriptionStatus.ACTIVE)
    grace_until = models.DateTimeField(null=True, blank=True)
    status_reason = models.CharField(max_length=320, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(profile__isnull=False, space__isnull=True) | Q(profile__isnull=True, space__isnull=False)),
                name="subs_runtime_subject_xor",
            ),
            models.UniqueConstraint(
                fields=["profile"],
                condition=Q(profile__isnull=False),
                name="subs_runtime_one_per_profile",
            ),
            models.UniqueConstraint(
                fields=["space"],
                condition=Q(space__isnull=False),
                name="subs_runtime_one_per_space",
            ),
            models.CheckConstraint(
                condition=~Q(status=SubscriptionStatus.CLOSED) | Q(closed_at__isnull=False),
                name="subs_runtime_closed_has_time",
            ),
        ]
        indexes = [
            models.Index(fields=["status", "grace_until"], name="subs_runtime_status_idx"),
        ]

    @property
    def subject_type(self):
        if self.profile_id and not self.space_id:
            return SubscriptionSubjectType.PROFILE
        if self.space_id and not self.profile_id:
            return SubscriptionSubjectType.SPACE
        return None

    @property
    def subject(self):
        return self.profile if self.profile_id else self.space

    def clean(self):
        super().clean()
        errors = {}
        if bool(self.profile_id) == bool(self.space_id):
            errors["profile"] = "Une Subscription appartient exactement à un Profile ou un Space."
        if self.status == SubscriptionStatus.CLOSED and self.closed_at is None:
            errors["closed_at"] = "Une Subscription fermée conserve sa date de fermeture."
        if self.status != SubscriptionStatus.CLOSED and self.closed_at is not None:
            errors["closed_at"] = "closed_at est réservé aux Subscriptions fermées."
        if self.status == SubscriptionStatus.GRACE and self.grace_until is None:
            errors["grace_until"] = "Une Subscription en grâce doit indiquer grace_until."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"Subscription {self.pk} — {self.subject_type or 'invalid'}"


class SubscriptionItemQuerySet(models.QuerySet):
    def delete(self):
        raise ValidationError("L'historique SubscriptionItem est conservé ; terminez l'Item au lieu de le supprimer.")


class SubscriptionItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="items")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name="subscription_items")
    plan_version = models.ForeignKey(PlanVersion, on_delete=models.PROTECT, related_name="subscription_items")
    item_type = models.CharField(max_length=12, choices=SubscriptionPlanType.choices)
    status = models.CharField(max_length=12, choices=SubscriptionItemStatus.choices, default=SubscriptionItemStatus.SCHEDULED)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField(null=True, blank=True)
    ended_reason = models.CharField(max_length=320, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = SubscriptionItemQuerySet.as_manager()

    IMMUTABLE_FIELDS = ("subscription_id", "plan_id", "plan_version_id", "item_type", "starts_at")

    class Meta:
        ordering = ["subscription", "starts_at", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["subscription"],
                condition=Q(status=SubscriptionItemStatus.ACTIVE, item_type=SubscriptionPlanType.BASE),
                name="subs_item_one_active_base",
            ),
            models.UniqueConstraint(
                fields=["subscription", "plan"],
                condition=Q(status=SubscriptionItemStatus.ACTIVE, item_type=SubscriptionPlanType.ADDON),
                name="subs_item_one_active_addon_plan",
            ),
            models.CheckConstraint(
                condition=~Q(status=SubscriptionItemStatus.ENDED) | Q(ends_at__isnull=False),
                name="subs_item_ended_has_time",
            ),
        ]
        indexes = [
            models.Index(fields=["subscription", "status", "item_type"], name="subs_item_active_lookup_idx"),
            models.Index(fields=["plan", "status"], name="subs_item_plan_status_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.plan_version_id and self.plan_id and self.plan_version.plan_id != self.plan_id:
            errors["plan_version"] = "La PlanVersion doit appartenir au Plan de l'Item."
        if self.plan_id and self.item_type != self.plan.plan_type:
            errors["item_type"] = "Le type de l'Item doit correspondre au type du Plan."
        if self.subscription_id and self.plan_id and self.subscription.subject_type != self.plan.subject_type:
            errors["plan"] = "Le Plan ne cible pas le type de sujet de cette Subscription."
        if self.status in {SubscriptionItemStatus.ACTIVE, SubscriptionItemStatus.SCHEDULED} and self.plan_version_id:
            if self.plan_version.status == PlanVersionStatus.DRAFT:
                errors["plan_version"] = "Une PlanVersion draft ne peut pas être utilisée par un Item actif ou planifié."
        if self.ends_at is not None and self.ends_at <= self.starts_at:
            errors["ends_at"] = "La fin de l'Item doit être postérieure à son début."
        if self.status == SubscriptionItemStatus.ENDED and self.ends_at is None:
            errors["ends_at"] = "Un Item terminé conserve sa date de fin."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).values(*self.IMMUTABLE_FIELDS).first()
            if previous:
                changed = [field for field in self.IMMUTABLE_FIELDS if previous[field] != getattr(self, field)]
                if changed:
                    raise ValidationError({field: "Le pinning et l'identité d'un SubscriptionItem sont immuables." for field in changed})
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("L'historique SubscriptionItem est conservé ; terminez l'Item au lieu de le supprimer.")

    def __str__(self):
        return f"{self.subscription_id} — {self.plan.code} v{self.plan_version.version}"


class EntitlementGrantQuerySet(models.QuerySet):
    def update(self, **kwargs):
        mutable = {"revoked_by", "revoked_by_id", "revoked_at", "revocation_reason", "updated_at"}
        if set(kwargs) - mutable:
            raise ValidationError("Un Grant existant est auditable ; seules ses données de révocation peuvent changer.")
        return super().update(**kwargs)

    def delete(self):
        raise ValidationError("Un Grant est auditable ; révoquez-le au lieu de le supprimer.")


class EntitlementGrant(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="entitlement_grants",
        null=True,
        blank=True,
    )
    space = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="entitlement_grants",
        null=True,
        blank=True,
    )
    feature = models.ForeignKey(FeatureDefinition, on_delete=models.PROTECT, related_name="grants")
    value = models.JSONField(encoder=DjangoJSONEncoder)
    valid_from = models.DateTimeField(default=timezone.now)
    valid_until = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=320)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="entitlement_grants_given",
        null=True,
        blank=True,
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    revoked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="entitlement_grants_revoked",
        null=True,
        blank=True,
    )
    revoked_at = models.DateTimeField(null=True, blank=True)
    revocation_reason = models.CharField(max_length=320, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EntitlementGrantQuerySet.as_manager()

    IMMUTABLE_FIELDS = (
        "profile_id", "space_id", "feature_id", "value", "valid_from", "valid_until", "reason", "granted_by_id"
    )

    class Meta:
        ordering = ["-granted_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(Q(profile__isnull=False, space__isnull=True) | Q(profile__isnull=True, space__isnull=False)),
                name="subs_grant_subject_xor",
            ),
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True) | Q(valid_until__gt=models.F("valid_from")),
                name="subs_grant_valid_window",
            ),
        ]
        indexes = [
            models.Index(fields=["profile", "feature", "valid_from"], name="subs_grant_profile_idx"),
            models.Index(fields=["space", "feature", "valid_from"], name="subs_grant_space_idx"),
            models.Index(fields=["revoked_at", "valid_until"], name="subs_grant_active_idx"),
        ]

    @property
    def subject_type(self):
        if self.profile_id and not self.space_id:
            return SubscriptionSubjectType.PROFILE
        if self.space_id and not self.profile_id:
            return SubscriptionSubjectType.SPACE
        return None

    def clean(self):
        super().clean()
        errors = {}
        if bool(self.profile_id) == bool(self.space_id):
            errors["profile"] = "Un EntitlementGrant cible exactement un Profile ou un Space."
        if self.valid_until is not None and self.valid_until <= self.valid_from:
            errors["valid_until"] = "valid_until doit être postérieur à valid_from."
        if self.feature_id:
            if not self.feature.is_active:
                errors["feature"] = "Une Feature inactive ne peut pas recevoir de nouveau Grant."
            elif self.subject_type and not self.feature.supports_subject_type(self.subject_type):
                errors["feature"] = "La Feature ne supporte pas ce type de sujet."
            else:
                try:
                    self.value = self.feature.normalize_entitlement_value(self.value)
                except ValidationError as exc:
                    errors.update(exc.message_dict)
        if self.revoked_at is None and (self.revoked_by_id or self.revocation_reason):
            errors["revoked_at"] = "Les données de révocation exigent revoked_at."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).values(*self.IMMUTABLE_FIELDS).first()
            if previous:
                changed = [field for field in self.IMMUTABLE_FIELDS if previous[field] != getattr(self, field)]
                if changed:
                    raise ValidationError({field: "Le contrat d'un Grant existant est immuable." for field in changed})
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Un Grant est auditable ; révoquez-le au lieu de le supprimer.")

    def __str__(self):
        return f"Grant {self.feature.code} — {self.subject_type or 'invalid'}"
