from django.core.exceptions import ValidationError
from django.db import transaction

from journeys.collaboration_models import JourneyArtifactKind, JourneyArtifactStatus
from journeys.collaboration_services import create_artifact
from payments.models import PaymentObligationProcessingMode
from payments.obligation_services import submit_payment_evidence


@transaction.atomic
def submit_external_payment_evidence_with_receipt(
    *,
    journey,
    obligation,
    actor,
    uploaded_file,
    paid_at,
    external_reference="",
):
    """Compose the canonical Artifact and PaymentEvidence owners for participant UX."""
    if obligation.journey_id != journey.pk:
        raise ValidationError("Cette obligation appartient à une autre démarche.")
    if obligation.processing_mode != PaymentObligationProcessingMode.EXTERNAL:
        raise ValidationError("Cette obligation n’accepte pas de preuve de paiement externe.")
    artifact = create_artifact(
        journey=journey,
        step=obligation.step,
        uploaded_file=uploaded_file,
        uploaded_by=actor,
        kind=JourneyArtifactKind.PAYMENT_RECEIPT,
        title=f"Preuve de paiement — {obligation.label}"[:220],
        status=JourneyArtifactStatus.SUBMITTED,
    )
    evidence = submit_payment_evidence(
        obligation=obligation,
        artifact=artifact,
        actor=actor,
        paid_at=paid_at,
        external_reference=external_reference,
    )
    return artifact, evidence
