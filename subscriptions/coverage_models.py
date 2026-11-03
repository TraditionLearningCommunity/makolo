from __future__ import annotations

import uuid
import calendar
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from .contracts import PlanVersionStatus, SubscriptionPlanType, SubscriptionSubjectType


class CoverageStatus(models.TextChoices):
    PENDING_PAYMENT = "pending_payment", "En attente de paiement"
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspendue"
    ENDED = "ended", "Terminée"


class AllocationStatus(models.TextChoices):
    INVITED = "invited", "Invitée"
    ACTIVE = "active", "Active"
    DECLINED = "declined", "Refusée"
    REVOKED = "revoked", "Révoquée"


class GroupCoveragePolicy(models.TextChoices):
    CURRENT_MEMBERS = "current_members", "Membres actuels"
    SNAPSHOT = "snapshot", "Population figée"


def coverage_period_end(starts_at, unit, count):
    """Calendar-accurate contractual period pinned to the published Billing Terms."""
    if count is None or count < 1:
        raise ValidationError("La période tarifaire est invalide.")
    if unit == "day":
        return starts_at + timedelta(days=count)
    if unit == "week":
        return starts_at + timedelta(weeks=count)
    if unit in {"month", "year"}:
        months = count if unit == "month" else 12 * count
        zero_based = starts_at.month - 1 + months
        year = starts_at.year + zero_based // 12
        month = zero_based % 12 + 1
        day = min(starts_at.day, calendar.monthrange(year, month)[1])
        return starts_at.replace(year=year, month=month, day=day)
    raise ValidationError("Unité de période tarifaire inconnue.")


class SubscriptionCoverage(models.Model):
    """A purchased, version-pinned benefit pool. Never a beneficiary's Subscription."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payer_profile = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name="funded_subscription_coverages",
    )
    payer_space = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT,
        null=True, blank=True, related_name="funded_subscription_coverages",
    )
    plan_version = models.ForeignKey(
        "subscriptions.PlanVersion", on_delete=models.PROTECT,
        related_name="funded_coverages",
    )
    billing_terms = models.ForeignKey(
        "subscriptions.PlanVersionBillingTerms", on_delete=models.PROTECT,
        related_name="funded_coverages",
    )
    purchased_quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(
        max_length=20, choices=CoverageStatus.choices,
        default=CoverageStatus.PENDING_PAYMENT,
    )
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField()
    request_key = models.CharField(max_length=128, unique=True)
    renewal_of = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="renewals",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="created_funded_coverages",
    )
    state_reason = models.CharField(max_length=320, blank=True)
    state_changed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    IMMUTABLE_FIELDS = (
        "payer_profile_id", "payer_space_id", "plan_version_id", "billing_terms_id",
        "purchased_quantity", "starts_at", "ends_at", "request_key", "renewal_of_id",
    )

    class Meta:
        ordering = ["-created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(payer_profile__isnull=False, payer_space__isnull=True)
                    | Q(payer_profile__isnull=True, payer_space__isnull=False)
                ),
                name="subs_coverage_payer_xor",
            ),
            models.CheckConstraint(
                condition=Q(purchased_quantity__gte=1),
                name="subs_coverage_quantity_positive",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__gt=models.F("starts_at")),
                name="subs_coverage_window_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["payer_profile", "status"], name="subs_coverage_payer_p_idx"),
            models.Index(fields=["payer_space", "status"], name="subs_coverage_payer_s_idx"),
            models.Index(fields=["plan_version", "status"], name="subs_coverage_version_idx"),
        ]

    @property
    def payer(self):
        return self.payer_profile if self.payer_profile_id else self.payer_space

    def clean(self):
        super().clean()
        errors = {}
        if bool(self.payer_profile_id) == bool(self.payer_space_id):
            errors["payer_profile"] = "Le financeur est exactement un Profil ou un Espace."
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "La couverture doit avoir une période non vide."
        if self.plan_version_id and self.billing_terms_id:
            if self.billing_terms.plan_version_id != self.plan_version_id:
                errors["billing_terms"] = "Les termes doivent appartenir à la version figée."
            if self._state.adding and self.plan_version.status != PlanVersionStatus.PUBLISHED:
                errors["plan_version"] = "Une nouvelle couverture exige une version publiée."
            if self._state.adding and not self.plan_version.plan.is_active:
                errors["plan_version"] = "Une formule inactive ne peut être achetée."
            if not self.billing_terms.coverage_enabled:
                errors["billing_terms"] = "Cette offre ne permet pas de couverture financée."
            if self.starts_at and self.ends_at:
                expected_end = coverage_period_end(
                    self.starts_at,
                    self.billing_terms.billing_period_unit,
                    self.billing_terms.billing_period_count,
                )
                if self.ends_at != expected_end:
                    errors["ends_at"] = "La période financée doit correspondre à un cycle tarifaire complet."
            if self.purchased_quantity is not None and self.purchased_quantity > self.billing_terms.coverage_max_quantity:
                errors["purchased_quantity"] = "La quantité dépasse le plafond de l'offre."
            if self.billing_terms.coverage_pricing_mode == "flat" and self.purchased_quantity != self.billing_terms.coverage_max_quantity:
                errors["purchased_quantity"] = "Une offre forfaitaire réserve exactement sa capacité prévue."
        if self.renewal_of_id:
            previous = self.renewal_of
            if previous.pk == self.pk or previous.plan_version_id != self.plan_version_id:
                errors["renewal_of"] = "Un renouvellement doit conserver la version contractuelle."
            if previous.payer_profile_id != self.payer_profile_id or previous.payer_space_id != self.payer_space_id:
                errors["renewal_of"] = "Le financeur d'un renouvellement doit être identique."
            if self.starts_at < previous.ends_at:
                errors["starts_at"] = "Un renouvellement ne chevauche pas sa période d'origine."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).values(*self.IMMUTABLE_FIELDS, "status").first()
            if previous:
                changed = [key for key in self.IMMUTABLE_FIELDS if previous[key] != getattr(self, key)]
                if changed:
                    raise ValidationError({key: "Le contrat acheté est immuable." for key in changed})
                if previous["status"] == CoverageStatus.ENDED and self.status != CoverageStatus.ENDED:
                    raise ValidationError("Une couverture terminée reste historique.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Une couverture historique ne se supprime pas.")


class SubscriptionCoverageAllocation(models.Model):
    """One beneficiary or group scope, with explicit consent and source provenance."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    coverage = models.ForeignKey(
        SubscriptionCoverage, on_delete=models.PROTECT, related_name="allocations",
    )
    profile = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
        null=True, blank=True, related_name="subscription_coverage_allocations",
    )
    space = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT,
        null=True, blank=True, related_name="subscription_coverage_allocations",
    )
    group = models.ForeignKey(
        "groups.Group", on_delete=models.PROTECT,
        null=True, blank=True, related_name="subscription_coverage_scopes",
    )
    group_parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, null=True, blank=True,
        related_name="member_allocations",
    )
    group_policy = models.CharField(
        max_length=24, choices=GroupCoveragePolicy.choices,
        default=GroupCoveragePolicy.CURRENT_MEMBERS,
    )
    group_snapshot = models.ForeignKey(
        "groups.GroupSnapshot", on_delete=models.PROTECT,
        null=True, blank=True, related_name="subscription_coverage_scopes",
    )
    status = models.CharField(
        max_length=16, choices=AllocationStatus.choices,
        default=AllocationStatus.INVITED,
    )
    selected_base = models.BooleanField(default=False)
    selected_at = models.DateTimeField(null=True, blank=True)
    starts_at = models.DateTimeField(default=timezone.now)
    ends_at = models.DateTimeField()
    request_key = models.CharField(max_length=128)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="created_coverage_allocations",
    )
    accepted_at = models.DateTimeField(null=True, blank=True)
    state_changed_at = models.DateTimeField(null=True, blank=True)
    state_reason = models.CharField(max_length=320, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    IMMUTABLE_FIELDS = (
        "coverage_id", "profile_id", "space_id", "group_id", "group_parent_id",
        "group_policy", "group_snapshot_id", "starts_at", "ends_at", "request_key",
    )

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(profile__isnull=False, space__isnull=True, group__isnull=True)
                    | Q(profile__isnull=True, space__isnull=False, group__isnull=True)
                    | Q(profile__isnull=True, space__isnull=True, group__isnull=False)
                ),
                name="subs_allocation_target_xor",
            ),
            models.CheckConstraint(
                condition=Q(ends_at__gt=models.F("starts_at")),
                name="subs_allocation_window_valid",
            ),
            models.CheckConstraint(
                condition=Q(selected_base=False) | Q(status=AllocationStatus.ACTIVE),
                name="subs_allocation_selected_active",
            ),
            models.UniqueConstraint(
                fields=["coverage", "request_key"],
                name="subs_allocation_idempotency",
            ),
        ]
        indexes = [
            models.Index(fields=["profile", "status"], name="subs_allocation_prof_idx"),
            models.Index(fields=["space", "status"], name="subs_allocation_space_idx"),
            models.Index(fields=["coverage", "status"], name="subs_allocation_pool_idx"),
        ]

    @property
    def target(self):
        return self.profile or self.space or self.group

    def clean(self):
        super().clean()
        errors = {}
        if sum((bool(self.profile_id), bool(self.space_id), bool(self.group_id))) != 1:
            errors["profile"] = "L'attribution cible exactement un Profil, un Espace ou un Groupe."
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            errors["ends_at"] = "L'attribution doit avoir une période non vide."
        if self.coverage_id:
            version = self.coverage.plan_version
            if self.group_id and version.plan.subject_type != SubscriptionSubjectType.PROFILE:
                errors["group"] = "Un Groupe qualifie uniquement des bénéficiaires personnels."
            if self.profile_id and version.plan.subject_type != SubscriptionSubjectType.PROFILE:
                errors["profile"] = "Cette offre ne cible pas les Profils."
            if self.space_id and version.plan.subject_type != SubscriptionSubjectType.SPACE:
                errors["space"] = "Cette offre ne cible pas les Espaces."
            if self.starts_at and self.ends_at and (
                self.starts_at < self.coverage.starts_at or self.ends_at > self.coverage.ends_at
            ):
                errors["ends_at"] = "L'attribution doit rester dans la période financée."
        if self.group_parent_id:
            parent = self.group_parent
            if parent.pk == self.pk or parent.group_id is None or parent.coverage_id != self.coverage_id:
                errors["group_parent"] = "Le parent doit être une attribution de Groupe dans la même couverture."
            if not self.profile_id:
                errors["group_parent"] = "Seul un Profil peut recevoir une attribution issue d'un Groupe."
        if self.group_snapshot_id:
            if not self.group_id or self.group_snapshot.group_id != self.group_id:
                errors["group_snapshot"] = "Le snapshot doit appartenir au Groupe cible."
            if self.group_policy != GroupCoveragePolicy.SNAPSHOT:
                errors["group_policy"] = "Le snapshot exige une politique de population figée."
        if self.group_id and self.group_policy == GroupCoveragePolicy.SNAPSHOT and not self.group_snapshot_id:
            errors["group_snapshot"] = "Une population figée exige un snapshot."
        if self.selected_base:
            if self.status != AllocationStatus.ACTIVE or not self.coverage_id or self.coverage.plan_version.plan.plan_type != SubscriptionPlanType.BASE:
                errors["selected_base"] = "Seule une BASE active peut être choisie."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).values(*self.IMMUTABLE_FIELDS, "status").first()
            if previous:
                changed = [key for key in self.IMMUTABLE_FIELDS if previous[key] != getattr(self, key)]
                if changed:
                    raise ValidationError({key: "L'attribution historique ne peut changer de destinataire." for key in changed})
                if previous["status"] in {AllocationStatus.DECLINED, AllocationStatus.REVOKED} and self.status != previous["status"]:
                    raise ValidationError("Une attribution terminée reste historique.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Une attribution historique ne se supprime pas.")
