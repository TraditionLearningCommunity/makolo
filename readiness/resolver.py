from django.core.exceptions import PermissionDenied
from django.utils import timezone

from journeys.models import JourneyStatus

from . import contributors  # noqa: F401 - registers built-in contributors
from . import questionnaire_contributor  # noqa: F401 - registers M2 contributor
from .registry import DEFAULT_CONTEXT, registry
from .types import ReadinessCheckState, ReadinessResult, ReadinessStatus


def reduce_readiness_status(checks):
    if any(check.state == ReadinessCheckState.BLOCKING for check in checks):
        return ReadinessStatus.BLOCKED
    if any(check.state == ReadinessCheckState.ACTION_REQUIRED for check in checks):
        return ReadinessStatus.ACTION_REQUIRED
    if any(check.state == ReadinessCheckState.WAITING for check in checks):
        return ReadinessStatus.WAITING
    return ReadinessStatus.READY


def resolve_readiness(
    subject,
    *,
    context=DEFAULT_CONTEXT,
    viewer=None,
    observed_at=None,
    status_resolver=None,
    next_action_states=(ReadinessCheckState.ACTION_REQUIRED,),
):
    observed_at = observed_at or timezone.now()
    checks = []
    for contributor in registry.all(context=context):
        checks.extend(contributor(subject, viewer, observed_at))
    status = status_resolver(checks, subject, observed_at) if status_resolver else reduce_readiness_status(checks)
    next_action = next(
        (
            check.next_action
            for state in next_action_states
            for check in checks
            if check.state == state and check.next_action
        ),
        None,
    )
    return ReadinessResult(status=status, checks=tuple(checks), next_action=next_action, observed_at=observed_at)


def _journey_status_for(checks, journey, now):
    status = reduce_readiness_status(checks)
    if status != ReadinessStatus.READY:
        return status
    if journey.status == JourneyStatus.FULFILLED:
        occurrence = journey.occurrence
        future_occurrence = bool(occurrence and occurrence.end_at and occurrence.end_at > now)
        future_access = any(
            access.status == "valid" and (access.valid_until is None or access.valid_until > now)
            for access in journey.accesses.all()
        )
        if not future_occurrence and not future_access:
            return ReadinessStatus.COMPLETE
    return ReadinessStatus.READY


def resolve_journey_readiness(journey, *, viewer=None, observed_at=None):
    if viewer is not None:
        if not getattr(viewer, "is_authenticated", False) or journey.beneficiary_id != getattr(viewer, "pk", None):
            raise PermissionDenied("Cette projection Readiness n’est pas visible pour ce participant.")
    return resolve_readiness(
        journey,
        context=DEFAULT_CONTEXT,
        viewer=viewer,
        observed_at=observed_at,
        status_resolver=_journey_status_for,
    )


def resolve_many(journeys, *, viewer=None, observed_at=None):
    observed_at = observed_at or timezone.now()
    return {
        journey.pk: resolve_journey_readiness(journey, viewer=viewer, observed_at=observed_at)
        for journey in journeys
    }
