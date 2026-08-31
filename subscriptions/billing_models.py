from __future__ import annotations

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

from payments.models import PaymentObligation, PaymentObligationReason

from .contracts import PlanVersionStatus
from .models import PlanVersion
from .runtime_models import Subscription
from .transition_models import SubscriptionTransition


class BillingPeriodUnit(models.TextChoices):
    DAY = "day", "Day"
    WEEK = "week", "Week"
    MONTH = "month", "Month"
    YEAR = "year", "Year"


class PlanVersionBillingTermsQuerySet(models.QuerySet):
    def update(self, **kwargs):
        if self.exclude(plan_version__status=PlanVersionStatus.DRAFT).exists():
            raise ValidationError("Les Billing Terms d’une PlanVersion publiée ou retirée sont immuables.")
        return super().update(**kwargs)

    def delete(self):
        if self.exclude(plan_version__status=PlanVersionStatus.DRAFT).exists():
            raise ValidationError("Les Billing Terms historiques ne peuvent pas être supprimés.")
        return super().delete()


class PlanVersionBillingTerms(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan_version = models.OneToOneField(
        PlanVersion,
        on_delete=models.PROTECT,
        related_name="billing_terms",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    currency = models.CharField(max_length=3, default="USD")
    billing_period_unit = models.CharField(max_length=8, choices=BillingPeriodUnit.choices)
    billing_period_count = models.PositiveIntegerField(default=1)
    payment_due_days = models.PositiveIntegerField(default=0)
    grace_period_days = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PlanVersionBillingTermsQuerySet.as_manager()

    IMMUTABLE_FIELDS = (
        "plan_version_id",
        "amount",
        "currency",
        "billing_period_unit",
        "billing_period_count",
        "payment_due_days",
        "grace_period_days",
    )

    class Meta:
        ordering = ["plan_version__plan", "plan_version__version"]
        constraints = [
            models.CheckConstraint(condition=Q(amount__gte=0), name="subs_billing_amount_nonnegative"),
            models.CheckConstraint(condition=Q(billing_period_count__gte=1), name="subs_billing_period_positive"),
        ]

    @property
    def is_free(self):
        return self.amount == Decimal("0.00")

    def clean(self):
        super().clean()
        errors = {}
        self.currency = (self.currency or "").strip().upper()
        if len(self.currency) != 3 or not self.currency.isalpha():
            errors["currency"] = "La devise doit être un code ISO 4217 de trois lettres."
        if self.amount is None or self.amount < 0:
            errors["amount"] = "Le montant des Billing Terms ne peut pas être négatif."
        if self.billing_period_count is None or self.billing_period_count < 1:
            errors["billing_period_count"] = "La cadence de billing doit être strictement positive."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.currency = (self.currency or "").strip().upper()
        if self.pk and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).values(*self.IMMUTABLE_FIELDS).first()
            if previous and self.plan_version.status != PlanVersionStatus.DRAFT:
                changed = [field for field in self.IMMUTABLE_FIELDS if previous[field] != getattr(self, field)]
                if changed:
                    raise ValidationError({field: "Les Billing Terms publiés sont historiques et immuables." for field in changed})
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.plan_version.status != PlanVersionStatus.DRAFT:
            raise ValidationError("Les Billing Terms historiques ne peuvent pas être supprimés.")
        return super().delete(*args, **kwargs)

    def __str__(self):
        return f"{self.plan_version} — {self.amount} {self.currency}/{self.billing_period_count} {self.billing_period_unit}"


class SubscriptionBillingObligation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.PROTECT, related_name="billing_obligation_links")
    transition = models.ForeignKey(
        SubscriptionTransition,
        on_delete=models.PROTECT,
        related_name="billing_obligation_links",
        null=True,
        blank=True,
    )
    billing_terms = models.ForeignKey(
        PlanVersionBillingTerms,
        on_delete=models.PROTECT,
        related_name="subscription_obligation_links",
    )
    obligation = models.OneToOneField(
        PaymentObligation,
        on_delete=models.PROTECT,
        related_name="subscription_billing_link",
    )
    billing_key = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["subscription", "billing_terms", "billing_key"],
                name="subs_billing_obligation_source_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["subscription", "created_at"], name="subs_billing_sub_idx"),
            models.Index(fields=["transition"], name="subs_billing_transition_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.billing_key = (self.billing_key or "").strip()
        if not self.billing_key:
            errors["billing_key"] = "Une obligation Subscription exige une provenance de billing."
        if self.transition_id and self.transition.subscription_id != self.subscription_id:
            errors["transition"] = "La Transition de billing doit appartenir à la même Subscription."
        if self.obligation_id:
            obligation = self.obligation
            if obligation.reason != PaymentObligationReason.SUBSCRIPTION:
                errors["obligation"] = "Le bridge de billing exige une obligation Subscription."
            if obligation.journey_id or obligation.commerce_order_id or obligation.step_id:
                errors["obligation"] = "Le billing Subscription ne doit pas créer de contexte Journey/Commerce."
            if not obligation.payee_platform:
                errors["obligation"] = "Makolo doit être le bénéficiaire de l’obligation Subscription."
            if self.subscription.profile_id:
                if obligation.payer_profile_id != self.subscription.profile_id or obligation.payer_space_id:
                    errors["obligation"] = "Le payer de l’obligation doit être le Profile souscripteur."
            elif self.subscription.space_id:
                if obligation.payer_space_id != self.subscription.space_id or obligation.payer_profile_id:
                    errors["obligation"] = "Le payer de l’obligation doit être le Space souscripteur."
            if self.billing_terms_id:
                if obligation.amount != self.billing_terms.amount:
                    errors["obligation"] = "Le montant doit rester celui des Billing Terms pinnés."
                if obligation.currency != self.billing_terms.currency:
                    errors["obligation"] = "La devise doit rester celle des Billing Terms pinnés."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.billing_key = (self.billing_key or "").strip()
        self.full_clean()
        return super().save(*args, **kwargs)
