from django.core.exceptions import PermissionDenied, ValidationError

from access.services import validate_access_credential

from .permissions import user_can_scan_activity


def scan_access_credential(
    *,
    token,
    actor,
    activity,
    occurrence=None,
    source="scanner",
    now=None,
):
    """Validate a canonical AccessCredential in an Activity/Occurrence context.

    This is the Scanner domain entry point. It deliberately knows nothing about
    Event, Ticket or ScanLog; the Events vertical wraps it for legacy UX and
    projection logging. ``now`` is injectable for deterministic domain tests;
    production callers keep the canonical real-time default.
    """
    if occurrence is not None and occurrence.activity_id != activity.pk:
        raise ValidationError("L’Occurrence de contrôle appartient à une autre Activity.")
    if not user_can_scan_activity(actor, activity, occurrence=occurrence):
        raise PermissionDenied("Vous n’êtes pas autorisé à contrôler les Accès dans ce contexte.")

    return validate_access_credential(
        token,
        controller=actor,
        authority_check=lambda controller, access: user_can_scan_activity(
            controller,
            activity,
            occurrence=occurrence,
        ),
        expected_activity=activity,
        expected_occurrence=occurrence,
        source=(source or "scanner")[:80],
        now=now,
    )
