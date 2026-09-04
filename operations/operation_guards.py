from django.core.exceptions import ValidationError
from django.utils import timezone

from activities.models import OccurrenceStatus


_TERMINAL_OCCURRENCE_STATUSES = {
    OccurrenceStatus.CANCELLED,
    OccurrenceStatus.COMPLETED,
}


def require_occurrence_live_actionable(occurrence, *, at=None):
    """Reject live mutations once the canonical Occurrence is over.

    Cleanup/terminal mutations may deliberately skip this guard. Offline or
    cached client state never overrides the current server-side Occurrence.
    """
    at = at or timezone.now()
    if occurrence.status in _TERMINAL_OCCURRENCE_STATUSES:
        raise ValidationError(
            {"occurrence": "Cette Occurrence n’accepte plus d’action opérationnelle live."}
        )
    if occurrence.end_at is not None and occurrence.end_at <= at:
        raise ValidationError(
            {"occurrence": "Cette Occurrence est terminée et n’accepte plus d’action opérationnelle live."}
        )
