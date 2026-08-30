from __future__ import annotations

import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from payments.models import PaymentObligation
from requirements.contracts import RequirementAssessmentState

from .contracts import (
    SubscriptionPlanType,
    SubscriptionTransitionKind,
    SubscriptionTransitionRequestOrigin,
    SubscriptionTransitionStatus,
)
from .eligibility_models import PlanRequirement
from .models import PlanVersion
from .runtime_models import Subscription, SubscriptionItem


OPEN_TRANSITION_STATUSES = (
    SubscriptionTransitionStatus.REQUESTED,
    SubscriptionTransitionStatus.IN_PROGRESS,
    SubscriptionTransitionStatus.READY,
)

TERMINAL_TRANSITION_STATUSES = (
    SubscriptionTransitionStatus.COMPLETED,
    SubscriptionTransitionStatus.REJECTED,
    SubscriptionTransitionStatus.CANCELLED,
    SubscriptionTransitionStatus.EXPIRED,
    SubscriptionTransitionStatus.FAILED,
)


class SubscriptionTransition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name="transitions")
    kind = models.CharField(max_length=20, choices=SubscriptionTransitionKind.choices)
    source_plan_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.PROTECT,
        related_name="subscription_transitions_from",
        null=True,
        blank=True,
    )
    target_plan_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.PROTECT,
        related_name="subscription_transitions_to",
    )
    source_item = models.ForeignKey(
        SubscriptionItem,
        on_delete=models.PROTECT,
        related_name="removal_transitions",
        null=True,
        blank=True,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="requested_subscription_transitions",
        null=True,
        blank=True,
    )
    request_origin = models.CharField(
        max_length=16,
        choices=SubscriptionTransitionRequestOrigin.choices,
        default=SubscriptionTransitionRequestOrigin.SELF_SERVICE,
    )
    status = models.CharField(
        max_length=16,
        choices=SubscriptionTransitionStatus.choices,
        default=SubscriptionTransitionStatus.REQUESTED,
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    ready_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    reason = models.CharField(max_length=500, blank=True)
    failure_code = models.CharField(max_length=120, blank=True)
    idempotency_key = models.CharField(max_length=128)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-requested_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["subscription", "idempotency_key"],
                name="subs_transition_idempotency_unique",
            ),
            models.UniqueConstraint(
                fields=["subscription"],
                condition=Q(status__in=OPEN_TRANSITION_STATUSES),
                name="subs_one_open_transition",
            ),
        ]
        indexes = [
            models.Index(fields=["subscription", "status"], name="subs_transition_status_idx"),
            models.Index(fields=["target_plan_version", "status"], name="subs_transition_target_idx"),
        ]

    def clean(self):
        super().clean()
        errors = {}
        key = (self.idempotency_key or "").strip()
        if not key:
            errors["idempotency_key"] = "Une Transition exige une clé d’idempotence."
        elif len(key) > 128:
            errors["idempotency_key"] = "La clé d’idempotence est trop longue."
        self.idempotency_key = key

        if self.subscription_id and self.target_plan_version_id:
            if self.target_plan_version.plan.subject_type != self.subscription.subject_type:
                errors["target_plan_version"] = "La cible ne correspond pas au type de sujet de la Subscription."

        if self.kind == SubscriptionTransitionKind.BASE_SWITCH:
            if self.target_plan_version_id and self.target_plan_version.plan.plan_type != SubscriptionPlanType.BASE:
                errors["target_plan_version"] = "Un base_switch doit cibler un Plan BASE."
            if not self.source_plan_version_id:
                errors["source_plan_version"] = "Un base_switch conserve la PlanVersion BASE source."
            if self.source_item_id:
                errors["source_item"] = "source_item est réservé à addon_remove."
        elif self.kind == SubscriptionTransitionKind.ADDON_ADD:
            if self.target_plan_version_id and self.target_plan_version.plan.plan_type != SubscriptionPlanType.ADDON:
                errors["target_plan_version"] = "Un addon_add doit cibler un Plan ADDON."
            if self.source_plan_version_id or self.source_item_id:
                errors["source_plan_version"] = "addon_add ne porte pas de source existante."
        elif self.kind == SubscriptionTransitionKind.ADDON_REMOVE:
            if self.target_plan_version_id and self.target_plan_version.plan.plan_type != SubscriptionPlanType.ADDON:
                errors["target_plan_version"] = "Un addon_remove doit pinner la PlanVersion ADDON retirée."
            if not self.source_item_id:
                errors["source_item"] = "Un addon_remove doit pinner l’Item actif retiré."
            elif self.source_item.subscription_id != self.subscription_id:
                errors["source_item"] = "L’Item retiré doit appartenir à la Subscription."
            elif self.source_item.plan_version_id != self.target_plan_version_id:
                errors["target_plan_version"] = "La cible d’un addon_remove doit être la version exacte de l’Item retiré."
            if self.source_plan_version_id:
                errors["source_plan_version"] = "addon_remove utilise source_item comme historique source."
        else:
            errors["kind"] = "Type de Transition inconnu."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            previous = type(self).objects.filter(pk=self.pk).values(
                "subscription_id",
                "kind",
                "source_plan_version_id",
                "target_plan_version_id",
                "source_item_id",
                "requested_by_id",
                "request_origin",
                "idempotency_key",
            ).first()
            if previous:
                immutable = {
                    "subscription_id": self.subscription_id,
                    "kind": self.kind,
                    "source_plan_version_id": self.source_plan_version_id,
                    "target_plan_version_id": self.target_plan_version_id,
                    "source_item_id": self.source_item_id,
                    "requested_by_id": self.requested_by_id,
                    "request_origin": self.request_origin,
                    "idempotency_key": self.idempotency_key,
                }
                changed = [name for name, value in immutable.items() if previous[name] != value]
                if changed:
                    raise ValidationError({name: "L’intention pinnée d’une Transition est immuable." for name in changed})
        self.full_clean()
        return super().save(*args, **kwargs)


class SubscriptionRequirementAssessment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transition = models.ForeignKey(SubscriptionTransition, on_delete=models.CASCADE, related_name="assessments")
    plan_requirement = models.ForeignKey(PlanRequirement, on_delete=models.PROTECT, related_name="subscription_assessments")
    state = models.CharField(
        max_length=20,
        choices=RequirementAssessmentState.choices,
        default=RequirementAssessmentState.UNASSESSED,
    )
    reason_code = models.CharField(max_length=160, blank=True)
    actual_value = models.JSONField(null=True, blank=True)
    expected_value = models.JSONField(null=True, blank=True)
    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="subscription_requirement_assessments",
        null=True,
        blank=True,
    )
    assessed_at = models.DateTimeField(null=True, blank=True)
    last_evaluated_at = models.DateTimeField(null=True, blank=True)
    note = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["transition", "plan_requirement__position", "created_at", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["transition", "plan_requirement"],
                name="subs_transition_requirement_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["transition", "state"], name="subs_assessment_state_idx"),
        ]

    def clean(self):
        super().clean()
        if self.transition_id and self.plan_requirement_id:
            if self.plan_requirement.plan_version_id != self.transition.target_plan_version_id:
                raise ValidationError({"plan_requirement": "L’Assessment doit appartenir à la PlanVersion pinnée par la Transition."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class AssessmentEventQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("L’historique d’Assessment est append-only.")

    def delete(self):
        raise ValidationError("L’historique d’Assessment est append-only.")


class SubscriptionRequirementAssessmentEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(
        SubscriptionRequirementAssessment,
        on_delete=models.PROTECT,
        related_name="events",
    )
    previous_state = models.CharField(max_length=20, choices=RequirementAssessmentState.choices)
    state = models.CharField(max_length=20, choices=RequirementAssessmentState.choices)
    reason_code = models.CharField(max_length=160, blank=True)
    assessed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="subscription_requirement_assessment_events",
        null=True,
        blank=True,
    )
    occurred_at = models.DateTimeField(auto_now_add=True)

    objects = AssessmentEventQuerySet.as_manager()

    class Meta:
        ordering = ["occurred_at", "id"]
        indexes = [models.Index(fields=["assessment", "occurred_at"], name="subs_assessment_event_idx")]

    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            raise ValidationError("Un événement d’Assessment existant est immuable.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("L’historique d’Assessment est append-only.")


class SubscriptionTransitionPaymentObligation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transition = models.ForeignKey(SubscriptionTransition, on_delete=models.CASCADE, related_name="payment_obligation_links")
    assessment = models.ForeignKey(
        SubscriptionRequirementAssessment,
        on_delete=models.CASCADE,
        related_name="payment_obligation_links",
    )
    obligation = models.ForeignKey(
        PaymentObligation,
        on_delete=models.PROTECT,
        related_name="subscription_transition_links",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="created_subscription_payment_obligation_links",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
        constraints = [
            models.UniqueConstraint(fields=["assessment", "obligation"], name="subs_assessment_obligation_unique"),
            models.UniqueConstraint(fields=["transition", "obligation"], name="subs_transition_obligation_unique"),
        ]
        indexes = [models.Index(fields=["transition", "assessment"], name="subs_transition_pay_idx")]

    def clean(self):
        super().clean()
        if self.assessment_id and self.transition_id and self.assessment.transition_id != self.transition_id:
            raise ValidationError({"assessment": "L’Assessment financier doit appartenir à la Transition."
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)
