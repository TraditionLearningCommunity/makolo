from django.core.exceptions import PermissionDenied
from django.utils import timezone

from journeys.models import JourneyStatus

from . import contributors  # noqa: F401 - registers built-in contributors
from . import questionnaire_contributor  # noqa: F401 - registers M2 contributor
from .registry import registry
from .types import ReadinessCheckState, ReadinessResult, ReadinessStatus


def _status_for(checks, *, journey, now):
    if any(check.state == ReadinessCheckState.BLOCKING for check in checks):
        return ReadinessStatus.BLOCKED
    if any(check.state == ReadinessCheckState.ACTION_REQUIRED for check in checks):
        return ReadinessStatus.ACTION_REQUIRED
    if any(check.state == ReadinessCheckState.WAITING for check in checks):
        return ReadinessStatus.WAITING
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
    observed_at = observed_at or timezone.now()
    if viewer is not None:
        if not getattr(viewer, "is_authenticated", False) or journey.beneficiary_id != getattr(viewer, "pk", None):
            raise PermissionDenied("Cette projection Readiness n’est pas visible pour ce participant.")
    checks = []
    for contributor in registry.all():
        checks.extend(contributor(journey, viewer, observed_at))
    status = _status_for(checks, journey=journey, now=observed_at)
    next_action = next(
        (check.next_action for check in checks if check.state == ReadinessCheckState.ACTION_REQUIRED and check.next_action),
        None,
    )
    return ReadinessResult(status=status, checks=tuple(checks), next_action=next_action, observed_at=observed_at)


def resolve_many(journeys, *, viewer=None, observed_at=None):
    observed_at = observed_at or timezone.now()
    return {
        journey.pk: resolve_journey_readiness(journey, viewer=viewer, observed_at=observed_at)
        for journey in journeys
    }
