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
    coverage_enabled = models.BooleanField(default=False)
    coverage_pricing_mode = models.CharField(
        max_length=12, choices=[("flat", "Forfait"), ("per_seat", "Par bénéficiaire")],
        default="flat",
    )
    coverage_max_quantity = models.PositiveIntegerField(default=1)
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
        "coverage_enabled",
        "coverage_pricing_mode",
        "coverage_max_quantity",
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
        if self.coverage_max_quantity is None or self.coverage_max_quantity < 1:
            errors["coverage_max_quantity"] = "Le plafond de bénéficiaires doit être positif."
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
    subscription = models.ForeignKey(
        Subscription, on_delete=models.PROTECT, related_name="billing_obligation_links",
        null=True, blank=True,
    )
    coverage = models.ForeignKey(
        "subscriptions.SubscriptionCoverage", on_delete=models.PROTECT,
        related_name="billing_obligation_links", null=True, blank=True,
    )
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
            models.UniqueConstraint(
                fields=["coverage", "billing_terms", "billing_key"],
                condition=Q(coverage__isnull=False),
                name="subs_billing_coverage_source_unique",
            ),
            models.CheckConstraint(
                condition=(
                    Q(subscription__isnull=False, coverage__isnull=True)
                    | Q(subscription__isnull=True, coverage__isnull=False)
                ),
                name="subs_billing_source_xor",
            ),
        ]
        indexes = [
            models.Index(fields=["subscription", "created_at"], name="subs_billing_sub_idx"),
            models.Index(fields=["transition"], name="subs_billing_transition_idx"),
            models.Index(fields=["coverage", "created_at"], name="subs_billing_cov_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        self.billing_key = (self.billing_key or "").strip()
        if not self.billing_key:
            errors["billing_key"] = "Une obligation Subscription exige une provenance de billing."
        if bool(self.subscription_id) == bool(self.coverage_id):
            errors["subscription"] = "Facturation ordinaire XOR couverture financée."
        if self.transition_id and (
            self.subscription_id is None or self.transition.subscription_id != self.subscription_id
        ):
            errors["transition"] = "La Transition doit appartenir à la Subscription ordinaire."
        if self.coverage_id:
            if self.transition_id:
                errors["transition"] = "Une couverture n'emprunte pas une Transition personnelle."
            if self.billing_terms_id and self.billing_terms_id != self.coverage.billing_terms_id:
                errors["billing_terms"] = "Utiliser les termes figés de la couverture."
        if self.obligation_id:
            obligation = self.obligation
            if obligation.reason != PaymentObligationReason.SUBSCRIPTION:
                errors["obligation"] = "Le bridge de billing exige une obligation Subscription."
            if obligation.journey_id or obligation.commerce_order_id or obligation.step_id:
                errors["obligation"] = "Le billing Subscription ne doit pas créer de contexte Journey/Commerce."
            if not obligation.payee_platform:
                errors["obligation"] = "Makolo doit être le bénéficiaire de l’obligation Subscription."
            if self.coverage_id:
                source = self.coverage
                if obligation.payer_profile_id != source.payer_profile_id or obligation.payer_space_id != source.payer_space_id:
                    errors["obligation"] = "Le payeur doit être le financeur de la couverture."
                if self.billing_terms_id:
                    amount = self.billing_terms.amount
                    if self.billing_terms.coverage_pricing_mode == "per_seat":
                        amount *= source.purchased_quantity
                    if obligation.amount != amount:
                        errors["obligation"] = "Le montant doit respecter le tarif de couverture figé."
            elif self.subscription_id:
                if self.subscription.profile_id:
                    if obligation.payer_profile_id != self.subscription.profile_id or obligation.payer_space_id:
                        errors["obligation"] = "Le payer doit être le Profil souscripteur."
                elif self.subscription.space_id:
                    if obligation.payer_space_id != self.subscription.space_id or obligation.payer_profile_id:
                        errors["obligation"] = "Le payer doit être l'Espace souscripteur."
                if self.billing_terms_id and obligation.amount != self.billing_terms.amount:
                    errors["obligation"] = "Le montant doit rester celui des Billing Terms pinnés."
            if self.billing_terms_id and obligation.currency != self.billing_terms.currency:
                errors["obligation"] = "La devise doit rester celle des Billing Terms pinnés."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.billing_key = (self.billing_key or "").strip()
        self.full_clean()
        return super().save(*args, **kwargs)
