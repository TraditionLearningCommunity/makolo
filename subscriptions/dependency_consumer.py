from __future__ import annotations

from domain_events.contracts import DomainEventType
from domain_events.registry import register_consumer
from domain_events.services import emit_domain_event
from organizations.models import Organization
from requirements.registry import RequirementRegistryError, registry

from .contracts import (
    AcquisitionMode,
    CatalogVisibility,
    PlanEligibilityStatus,
    PlanVersionStatus,
    RequirementPhase,
    SubscriptionSubjectType,
)
from .eligibility import resolve_plan_eligibility
from .eligibility_models import PlanRequirement
from .models import PlanVersion
from .ongoing_services import evaluate_subscription_ongoing_requirements
from .runtime_models import Subscription


CONSUMER_NAME = "subscriptions.dependencies"
EVENT_TYPES = {DomainEventType.ORGANIZATION_TEAM_MEMBERSHIP_CHANGED}


def _evaluator_keys_for_event(event_type):
    keys = PlanRequirement.objects.exclude(evaluator_key="").values_list("evaluator_key", flat=True).distinct()
    dependent = []
    for key in keys:
        try:
            definition = registry.get(key)
        except RequirementRegistryError:
            continue
        if event_type in definition.dependency_events:
            dependent.append(key)
    return tuple(dependent)


def _emit_available_plan(space, version):
    emit_domain_event(
        event_type=DomainEventType.SUBSCRIPTION_ELIGIBILITY_AVAILABLE,
        source_type="subscription_eligibility",
        source_id=str(space.pk),
        space_id=space.pk,
        payload={
            "subject_type": SubscriptionSubjectType.SPACE,
            "subject_id": str(space.pk),
            "space_id": str(space.pk),
            "plan_version_id": str(version.pk),
        },
        idempotency_key=f"subscription-eligibility:{space.pk}:{version.pk}",
    )


def consume_subscription_dependency_event(event):
    payload = event.payload or {}
    space_id = payload.get("space_id")
    if not space_id:
        return
    space = Organization.objects.filter(pk=space_id).first()
    if not space:
        return

    evaluator_keys = _evaluator_keys_for_event(event.event_type)
    if not evaluator_keys:
        return

    subscription = Subscription.objects.filter(space=space).first()
    if subscription:
        evaluate_subscription_ongoing_requirements(subscription.pk)

    versions = (
        PlanVersion.objects.filter(
            status=PlanVersionStatus.PUBLISHED,
            plan__subject_type=SubscriptionSubjectType.SPACE,
            catalog_visibility=CatalogVisibility.PUBLIC,
            acquisition_mode=AcquisitionMode.SELF_SERVICE,
            requirements__phase=RequirementPhase.ACQUISITION,
            requirements__evaluator_key__in=evaluator_keys,
        )
        .select_related("plan")
        .prefetch_related("requirements")
        .distinct()
    )
    for version in versions:
        result = resolve_plan_eligibility(space, version, self_service=True)
        if result.status == PlanEligibilityStatus.AVAILABLE:
            _emit_available_plan(space, version)


register_consumer(CONSUMER_NAME, consume_subscription_dependency_event, event_types=EVENT_TYPES)
