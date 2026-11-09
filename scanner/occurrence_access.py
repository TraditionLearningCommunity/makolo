"""Scanner for any Activity Occurrence, using canonical Access / AccessUse.

This is not an Event ticket adapter. No credential secrets, bearer tokens, or
beneficiary private data are emitted or persisted in presentation payloads.
"""
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from access.models import AccessUseResult
from .canonical_services import scan_access_credential
from operations.checkpoint_services import observe_checkpoint
from operations.models import CheckpointStatus, OccurrenceCheckpoint

from .permissions import get_active_assignment, user_can_scan_activity


@transaction.atomic
def control_occurrence_access(*, occurrence, actor, token, client_reference=""):
    """Server-authorized scan with an idempotent AccessUse and optional checkpoint.

    The assignment describes a checkpoint responsibility but NEVER grants
    scanner authority by itself. Access validation locks the affected records.
    """
    if not user_can_scan_activity(actor, occurrence.activity, occurrence=occurrence):
        raise PermissionDenied("Contrôle d'accès non autorisé pour cette Occurrence.")

    token = (token or "").strip()
    if not token or len(token) > 1024:
        raise ValidationError({"token": "Code absent ou non valide."})
    if not isinstance(client_reference, str) or len(client_reference) > 64:
        raise ValidationError({"client_reference": "Référence invalide."})

    assignment = get_active_assignment(actor, activity=occurrence.activity, occurrence=occurrence)
    checkpoint = None
    if assignment is not None and assignment.checkpoint_id:
        checkpoint = (
            OccurrenceCheckpoint.objects.select_for_update(of=("self",))
            .select_related("occurrence", "occurrence__activity")
            .get(pk=assignment.checkpoint_id)
        )
        if checkpoint.occurrence_id != occurrence.pk:
            raise PermissionDenied("Point de contrôle hors de cette Occurrence.")
        if not checkpoint.active or checkpoint.status != CheckpointStatus.OPEN:
            return {
                "accepted": False,
                "result": "checkpoint_unavailable",
                "message": "Ce point de contrôle n'est pas ouvert.",
                "controlled_at": None,
                "checkpoint_observed": False,
            }

    # Canonical Scanner -> Access path. Do not clone credential validation
    # or its idempotent use handling in an Occurrence-specific UI adapter.
    outcome = scan_access_credential(
        token=token,
        actor=actor,
        activity=occurrence.activity,
        occurrence=occurrence,
        source="scanner-occurrence",
        client_reference=client_reference,
    )
    observation = None
    if outcome.result == AccessUseResult.ACCEPTED and checkpoint is not None:
        if outcome.use is None:
            raise ValidationError("Contrôle accepté sans preuve AccessUse.")
        observation = observe_checkpoint(
            actor=actor,
            checkpoint=checkpoint,
            profile=outcome.access.beneficiary if outcome.access.beneficiary_id else None,
            external_beneficiary=(
                outcome.access.external_beneficiary
                if outcome.access.external_beneficiary_id else None
            ),
            source="scanner-occurrence",
            client_reference=client_reference,
            access_use=outcome.use,
            authority_check=lambda user, cp: (
                cp.pk == checkpoint.pk and
                user_can_scan_activity(
                    user, cp.occurrence.activity, occurrence=cp.occurrence,
                ) and
                (
                    (
                        current_assignment := get_active_assignment(
                            user,
                            activity=cp.occurrence.activity,
                            occurrence=cp.occurrence,
                        )
                    ) is not None
                    and current_assignment.pk == assignment.pk
                    and current_assignment.checkpoint_id == cp.pk
                )
            ),
        )
    return {
        "accepted": outcome.accepted,
        "result": outcome.result,
        "message": outcome.message,
        "controlled_at": (
            outcome.use.used_at.isoformat() if outcome.use else None
        ),
        "checkpoint_observed": observation is not None,
    }
