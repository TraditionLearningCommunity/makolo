from __future__ import annotations

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event

from .contracts import SubscriptionTransitionKind, SubscriptionTransitionStatus
from .transition_models import SubscriptionRequirementAssessment, SubscriptionTransition


_TRANSITION_EVENT_TYPES = {
    SubscriptionTransitionStatus.REQUESTED: DomainEventType.SUBSCRIPTION_TRANSITION_REQUESTED,
    SubscriptionTransitionStatus.READY: DomainEventType.SUBSCRIPTION_TRANSITION_READY,
    SubscriptionTransitionStatus.COMPLETED: DomainEventType.SUBSCRIPTION_TRANSITION_COMPLETED,
    SubscriptionTransitionStatus.REJECTED: DomainEventType.SUBSCRIPTION_TRANSITION_REJECTED,
    SubscriptionTransitionStatus.CANCELLED: DomainEventType.SUBSCRIPTION_TRANSITION_CANCELLED,
    SubscriptionTransitionStatus.FAILED: DomainEventType.SUBSCRIPTION_TRANSITION_FAILED,
    SubscriptionTransitionStatus.EXPIRED: DomainEventType.SUBSCRIPTION_TRANSITION_EXPIRED,
}


def _subscription_payload(subscription):
    payload = {
        "subscription_id": str(subscription.pk),
        "subject_type": subscription.subject_type,
        "subject_id": str(subscription.profile_id or subscription.space_id),
    }
    if subscription.space_id:
        payload["space_id"] = str(subscription.space_id)
    return payload


@receiver(pre_save, sender=SubscriptionTransition, dispatch_uid="subscriptions.transition.capture_previous_status")
def capture_transition_previous_status(sender, instance, **kwargs):
    if instance._state.adding:
        instance._s5_previous_status = None
        return
    instance._s5_previous_status = sender.objects.filter(pk=instance.pk).values_list("status", flat=True).first()


@receiver(post_save, sender=SubscriptionTransition, dispatch_uid="subscriptions.transition.domain_events")
def emit_transition_domain_events(sender, instance, created, **kwargs):
    previous_status = getattr(instance, "_s5_previous_status", None)
    if not created and previous_status == instance.status:
        return
    event_type = _TRANSITION_EVENT_TYPES.get(instance.status)
    if event_type is None:
        return

    payload = _subscription_payload(instance.subscription)
    payload.update(
        {
            "transition_id": str(instance.pk),
            "transition_kind": instance.kind,
            "plan_version_id": str(instance.target_plan_version_id),
            "old_state": previous_status,
            "new_state": instance.status,
        }
    )
    emit_domain_event(
        event_type=event_type,
        aggregate_type="subscription",
        aggregate_id=instance.subscription_id,
        payload=payload,
        actor=instance.requested_by,
        idempotency_key=f"subscription-transition:{instance.pk}:{event_type}",
    )

    if instance.status != SubscriptionTransitionStatus.COMPLETED:
        return
    if instance.kind == SubscriptionTransitionKind.BASE_SWITCH:
        product_event = DomainEventType.SUBSCRIPTION_PLAN_CHANGED
    elif instance.kind == SubscriptionTransitionKind.ADDON_ADD:
        product_event = DomainEventType.SUBSCRIPTION_ADDON_ACTIVATED
    else:
        product_event = DomainEventType.SUBSCRIPTION_ADDON_REMOVED
    emit_domain_event(
        event_type=product_event,
        aggregate_type="subscription",
        aggregate_id=instance.subscription_id,
        payload=payload,
        actor=instance.requested_by,
        idempotency_key=f"subscription-transition:{instance.pk}:{product_event}",
    )


@receiver(pre_save, sender=SubscriptionRequirementAssessment, dispatch_uid="subscriptions.assessment.capture_previous_state")
def capture_assessment_previous_state(sender, instance, **kwargs):
    if instance._state.adding:
        instance._s5_previous_state = None
        return
    instance._s5_previous_state = sender.objects.filter(pk=instance.pk).values_list("state", flat=True).first()


@receiver(post_save, sender=SubscriptionRequirementAssessment, dispatch_uid="subscriptions.assessment.domain_events")
def emit_assessment_domain_event(sender, instance, created, **kwargs):
    previous_state = getattr(instance, "_s5_previous_state", None)
    if created or previous_state == instance.state:
        return
    transition = instance.transition
    payload = _subscription_payload(transition.subscription)
    payload.update(
        {
            "transition_id": str(transition.pk),
            "assessment_id": str(instance.pk),
            "requirement_id": str(instance.plan_requirement_id),
            "disclosure": instance.plan_requirement.disclosure,
            "old_state": previous_state,
            "new_state": instance.state,
        }
    )
    emit_domain_event(
        event_type=DomainEventType.SUBSCRIPTION_REQUIREMENT_CHANGED,
        aggregate_type="subscription",
        aggregate_id=transition.subscription_id,
        payload=payload,
        actor=instance.assessed_by,
        idempotency_key=f"subscription-assessment:{instance.pk}:{instance.updated_at.isoformat()}:{instance.state}",
    )
