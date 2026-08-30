from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event
from requirements.contracts import RequirementAssessmentState, RequirementMode
from requirements.registry import registry

from .contracts import (
    RequirementFailurePolicy,
    RequirementPhase,
    SubscriptionItemStatus,
    SubscriptionStatus,
)
from .eligibility_models import PlanRequirement
from .ongoing_models import SubscriptionOngoingRequirementState
from .runtime_models import Subscription, SubscriptionItem


@dataclass(frozen=True)
class OngoingEvaluationSummary:
    subscription_id: str
    previous_status: str
    status: str
    evaluated_requirements: int
    unsatisfied_warn: int
    unsatisfied_grace: int
    unsatisfied_suspend: int
    grace_until: object = None


def _subject_payload(subscription):
    payload = {
        "subscription_id": str(subscription.pk),
        "subject_type": subscription.subject_type,
        "subject_id": str(subscription.profile_id or subscription.space_id),
    }
    if subscription.space_id:
        payload["space_id"] = str(subscription.space_id)
    return payload


def _emit_requirement_change(subscription, state_row, requirement, old_state):
    payload = _subject_payload(subscription)
    payload.update(
        {
            "requirement_id": str(requirement.pk),
            "disclosure": requirement.disclosure,
            "old_state": old_state,
            "new_state": state_row.state,
        }
    )
    emit_domain_event(
        event_type=DomainEventType.SUBSCRIPTION_REQUIREMENT_CHANGED,
        aggregate_type="subscription",
        aggregate_id=subscription.pk,
        payload=payload,
        idempotency_key=f"subscription-ongoing:{state_row.pk}:{state_row.updated_at.isoformat()}:{state_row.state}",
    )


def _emit_status_change(subscription, *, event_type, previous_status, now):
    payload = _subject_payload(subscription)
    payload.update(
        {
            "old_state": previous_status,
            "new_state": subscription.status,
            "grace_until": subscription.grace_until.isoformat() if subscription.grace_until else None,
        }
    )
    emit_domain_event(
        event_type=event_type,
        aggregate_type="subscription",
        aggregate_id=subscription.pk,
        payload=payload,
        idempotency_key=f"subscription-status:{subscription.pk}:{event_type}:{now.isoformat()}",
    )


def _active_ongoing_requirements(subscription, at):
    plan_version_ids = SubscriptionItem.objects.filter(
        subscription=subscription,
        status=SubscriptionItemStatus.ACTIVE,
        starts_at__lte=at,
    ).filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=at)).values_list("plan_version_id", flat=True)
    return PlanRequirement.objects.filter(
        plan_version_id__in=plan_version_ids,
        phase=RequirementPhase.ONGOING,
        mode=RequirementMode.AUTOMATIC,
    ).select_related("plan_version", "plan_version__plan")


@transaction.atomic
def evaluate_subscription_ongoing_requirements(subscription, *, now=None):
    """Evaluate automatic ongoing Requirements for one Subscription only.

    This function never scans Profiles, Spaces or Plans globally. It serializes the
    Subscription, evaluates only Requirements attached to its active Items, persists
    minimal change-detection state, then applies the aggregate warn/grace/suspend policy.
    """
    from django.db import models

    now = now or timezone.now()
    subscription_id = subscription.pk if isinstance(subscription, Subscription) else subscription
    subscription = (
        Subscription.objects.select_for_update()
        .select_related("profile", "space")
        .get(pk=subscription_id)
    )
    subject = subscription.profile or subscription.space
    previous_status = subscription.status

    plan_version_ids = (
        SubscriptionItem.objects.filter(
            subscription=subscription,
            status=SubscriptionItemStatus.ACTIVE,
            starts_at__lte=now,
        )
        .filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now))
        .values_list("plan_version_id", flat=True)
    )
    requirements = list(
        PlanRequirement.objects.filter(
            plan_version_id__in=plan_version_ids,
            phase=RequirementPhase.ONGOING,
            mode=RequirementMode.AUTOMATIC,
        ).order_by("plan_version_id", "position", "id")
    )

    warn = []
    grace = []
    suspend = []
    active_requirement_ids = []
    for requirement in requirements:
        active_requirement_ids.append(requirement.pk)
        result = registry.evaluate(requirement.evaluator_key, subject=subject, config=requirement.config)
        state_row = SubscriptionOngoingRequirementState.objects.select_for_update().filter(
            subscription=subscription,
            plan_requirement=requirement,
        ).first()
        old_state = state_row.state if state_row else None
        changed = state_row is None or state_row.state != result.state or state_row.reason_code != result.reason_code
        if state_row is None:
            state_row = SubscriptionOngoingRequirementState(
                subscription=subscription,
                plan_requirement=requirement,
                state=result.state,
                reason_code=result.reason_code,
                last_evaluated_at=now,
            )
        else:
            state_row.state = result.state
            state_row.reason_code = result.reason_code
            state_row.last_evaluated_at = now

        if result.state == RequirementAssessmentState.UNSATISFIED:
            if state_row.first_unsatisfied_at is None:
                state_row.first_unsatisfied_at = now
        else:
            state_row.first_unsatisfied_at = None
        state_row.save()
        if changed:
            _emit_requirement_change(subscription, state_row, requirement, old_state)

        if not requirement.is_mandatory or result.state != RequirementAssessmentState.UNSATISFIED:
            continue
        if requirement.failure_policy == RequirementFailurePolicy.WARN:
            warn.append(requirement)
        elif requirement.failure_policy == RequirementFailurePolicy.GRACE:
            grace.append(requirement)
        elif requirement.failure_policy == RequirementFailurePolicy.SUSPEND:
            suspend.append(requirement)

    SubscriptionOngoingRequirementState.objects.filter(subscription=subscription).exclude(
        plan_requirement_id__in=active_requirement_ids
    ).delete()

    event_type = None
    if suspend:
        subscription.status = SubscriptionStatus.SUSPENDED
        subscription.grace_until = None
        subscription.status_reason = "ongoing_requirement_unsatisfied"
        if previous_status != SubscriptionStatus.SUSPENDED:
            event_type = DomainEventType.SUBSCRIPTION_SUSPENDED
    elif grace:
        if previous_status == SubscriptionStatus.SUSPENDED and subscription.status_reason.startswith("ongoing_"):
            subscription.status = SubscriptionStatus.SUSPENDED
            subscription.grace_until = None
            subscription.status_reason = "ongoing_grace_expired"
        elif subscription.status == SubscriptionStatus.GRACE and subscription.grace_until:
            if subscription.grace_until <= now:
                subscription.status = SubscriptionStatus.SUSPENDED
                subscription.grace_until = None
                subscription.status_reason = "ongoing_grace_expired"
                event_type = DomainEventType.SUBSCRIPTION_SUSPENDED
        elif subscription.status == SubscriptionStatus.ACTIVE:
            grace_days = min((item.grace_period_days or 0) for item in grace)
            subscription.status = SubscriptionStatus.GRACE
            subscription.grace_until = now + timedelta(days=grace_days)
            subscription.status_reason = "ongoing_requirement_grace"
            event_type = DomainEventType.SUBSCRIPTION_GRACE_STARTED
    elif previous_status == SubscriptionStatus.GRACE and subscription.status_reason.startswith("ongoing_"):
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.grace_until = None
        subscription.status_reason = ""
        event_type = DomainEventType.SUBSCRIPTION_GRACE_ENDED
    elif previous_status == SubscriptionStatus.SUSPENDED and subscription.status_reason.startswith("ongoing_"):
        subscription.status = SubscriptionStatus.ACTIVE
        subscription.grace_until = None
        subscription.status_reason = ""
        event_type = DomainEventType.SUBSCRIPTION_REACTIVATED

    if (
        subscription.status != previous_status
        or subscription.grace_until != Subscription.objects.filter(pk=subscription.pk).values_list("grace_until", flat=True).first()
    ):
        subscription.save(update_fields=["status", "grace_until", "status_reason", "updated_at"])
    if event_type:
        _emit_status_change(subscription, event_type=event_type, previous_status=previous_status, now=now)

    return OngoingEvaluationSummary(
        subscription_id=str(subscription.pk),
        previous_status=previous_status,
        status=subscription.status,
        evaluated_requirements=len(requirements),
        unsatisfied_warn=len(warn),
        unsatisfied_grace=len(grace),
        unsatisfied_suspend=len(suspend),
        grace_until=subscription.grace_until,
    )
