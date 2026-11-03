"""Minimal, privacy-safe domain facts for financed Subscription coverages."""
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event

from .coverage_models import SubscriptionCoverage, SubscriptionCoverageAllocation


@receiver(pre_save, sender=SubscriptionCoverage, dispatch_uid="subscriptions.coverage.previous")
def capture_coverage_status(sender, instance, raw=False, **kwargs):
    instance._coverage_previous_status = (
        None if raw or instance._state.adding
        else sender.objects.filter(pk=instance.pk).values_list("status", flat=True).first()
    )


@receiver(post_save, sender=SubscriptionCoverage, dispatch_uid="subscriptions.coverage.domain_events")
def coverage_events(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    before = getattr(instance, "_coverage_previous_status", None)
    if not created and before == instance.status:
        return
    event_type = (
        DomainEventType.SUBSCRIPTION_COVERAGE_CREATED
        if created else DomainEventType.SUBSCRIPTION_COVERAGE_STATUS_CHANGED
    )
    key = (
        f"coverage:{instance.pk}:created" if created
        else f"coverage:{instance.pk}:{instance.status}:{instance.state_changed_at.isoformat() if instance.state_changed_at else instance.updated_at.isoformat()}"
    )
    emit_domain_event(
        event_type=event_type, source_type="subscription_coverage",
        source_id=str(instance.pk), space_id=instance.payer_space_id,
        idempotency_key=key,
        payload={
            "coverage_id": str(instance.pk),
            "plan_version_id": str(instance.plan_version_id),
            "status": instance.status,
        },
    )


@receiver(pre_save, sender=SubscriptionCoverageAllocation, dispatch_uid="subscriptions.coverage.allocation_previous")
def capture_allocation_state(sender, instance, raw=False, **kwargs):
    instance._coverage_allocation_previous = (
        None if raw or instance._state.adding
        else sender.objects.filter(pk=instance.pk).values("status", "selected_base").first()
    )


@receiver(post_save, sender=SubscriptionCoverageAllocation, dispatch_uid="subscriptions.coverage.allocation_events")
def coverage_allocation_events(sender, instance, created, raw=False, **kwargs):
    if raw:
        return
    before = getattr(instance, "_coverage_allocation_previous", None)
    if not created and before == {
        "status": instance.status,
        "selected_base": instance.selected_base,
    }:
        return
    event_type = (
        DomainEventType.SUBSCRIPTION_COVERAGE_ALLOCATION_CREATED
        if created else DomainEventType.SUBSCRIPTION_COVERAGE_ALLOCATION_CHANGED
    )
    key = (
        f"coverage-allocation:{instance.pk}:created" if created
        else f"coverage-allocation:{instance.pk}:{instance.status}:{int(instance.selected_base)}:"
             f"{instance.state_changed_at.isoformat() if instance.state_changed_at else instance.updated_at.isoformat()}"
    )
    emit_domain_event(
        event_type=event_type, source_type="subscription_coverage_allocation",
        source_id=str(instance.pk), space_id=instance.coverage.payer_space_id,
        idempotency_key=key,
        payload={
            "coverage_id": str(instance.coverage_id),
            "allocation_id": str(instance.pk),
            "status": instance.status,
            "selected_base": instance.selected_base,
        },
    )
