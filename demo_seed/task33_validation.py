from __future__ import annotations

from journeys.models import JourneyStatus
from payments.models import (
    Payment,
    PaymentEvidence,
    PaymentEvidenceStatus,
    PaymentObligation,
    PaymentObligationProcessingMode,
    PaymentObligationReason,
    PaymentObligationStatus,
    PaymentProvider,
    PaymentStatus,
)
from requirements.contracts import RequirementAssessmentState
from services.models import (
    ServiceCurrentOutcome,
    ServiceJourneyContext,
    ServiceOutcomeEvent,
    ServiceOutcomeEventType,
    ServiceSubmission,
    ServiceSubmissionStatus,
)

from .common import stable_uuid


class Task33BetaValidationError(RuntimeError):
    pass


def _require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def assert_task33_beta_coverage() -> dict[str, int]:
    errors: list[str] = []

    commerce_payments = Payment.objects.filter(
        metadata__seed="makolo-beta",
        status=PaymentStatus.SUCCEEDED,
        commerce_order__isnull=False,
    )
    _require(commerce_payments.exists(), "T33: Payment Commerce bêta réussi absent", errors)
    _require(
        not commerce_payments.filter(obligation__isnull=True).exists(),
        "T33: Payment Commerce bêta sans PaymentObligation",
        errors,
    )
    _require(
        not PaymentObligation.objects.filter(
            payments__in=commerce_payments,
        ).exclude(
            reason=PaymentObligationReason.COMMERCE,
            status=PaymentObligationStatus.SATISFIED,
        ).exists(),
        "T33: obligation Commerce bêta incohérente",
        errors,
    )

    sandbox = PaymentObligation.objects.filter(source_key="beta:t33:opportunity-fee:sandbox").first()
    _require(sandbox is not None, "T33: obligation Opportunity sandbox absente", errors)
    if sandbox is not None:
        _require(sandbox.processing_mode == PaymentObligationProcessingMode.MAKOLO_PROVIDER, "T33: mauvais processing_mode sandbox", errors)
        _require(sandbox.status == PaymentObligationStatus.SATISFIED, "T33: obligation sandbox non satisfaite", errors)
        _require(bool(sandbox.external_payee_name), "T33: bénéficiaire économique externe sandbox absent", errors)
        _require(
            Payment.objects.filter(
                obligation=sandbox,
                provider=PaymentProvider.SANDBOX,
                status=PaymentStatus.SUCCEEDED,
            ).count() == 1,
            "T33: tentative sandbox réussie unique absente",
            errors,
        )
        _require(
            sandbox.service_requirement_links.filter(
                assessment__status=RequirementAssessmentState.SATISFIED,
            ).exists(),
            "T33: Assessment financier sandbox non synchronisé",
            errors,
        )

    external = PaymentObligation.objects.filter(source_key="beta:t33:opportunity-fee:external").first()
    _require(external is not None, "T33: obligation Opportunity externe absente", errors)
    if external is not None:
        _require(external.processing_mode == PaymentObligationProcessingMode.EXTERNAL, "T33: mauvais processing_mode externe", errors)
        _require(external.status == PaymentObligationStatus.SATISFIED, "T33: obligation externe non satisfaite", errors)
        _require(not Payment.objects.filter(obligation=external).exists(), "T33: faux Payment créé pour paiement externe", errors)
        _require(
            PaymentEvidence.objects.filter(
                obligation=external,
                status=PaymentEvidenceStatus.VERIFIED,
            ).exists(),
            "T33: PaymentEvidence vérifiée absente",
            errors,
        )
        _require(
            external.service_requirement_links.filter(
                assessment__status=RequirementAssessmentState.SATISFIED,
            ).exists(),
            "T33: Assessment financier externe non synchronisé",
            errors,
        )

    submission_context = ServiceJourneyContext.objects.filter(
        pk=stable_uuid("task33-service-context:submission-outcome")
    ).select_related("journey").first()
    _require(submission_context is not None, "T33: contexte Submission/Outcome absent", errors)
    if submission_context is not None:
        _require(submission_context.journey.status == JourneyStatus.FULFILLED, "T33: Journey de résultat externe non fulfilled", errors)
        _require(
            ServiceSubmission.objects.filter(
                context=submission_context,
                status__in={ServiceSubmissionStatus.SUBMITTED, ServiceSubmissionStatus.ACKNOWLEDGED},
            ).exists(),
            "T33: ServiceSubmission réellement soumise absente",
            errors,
        )
        _require(
            ServiceOutcomeEvent.objects.filter(
                context=submission_context,
                event_type=ServiceOutcomeEventType.UNSUCCESSFUL,
            ).exists(),
            "T33: outcome unsuccessful absent",
            errors,
        )
        _require(
            submission_context.current_outcome == ServiceCurrentOutcome.UNSUCCESSFUL,
            "T33: current_outcome doit rester unsuccessful indépendamment de Journey.fulfilled",
            errors,
        )

    if errors:
        raise Task33BetaValidationError("Validation bêta T33 échouée: " + "; ".join(errors))

    return {
        "t33_commerce_obligations": PaymentObligation.objects.filter(
            reason=PaymentObligationReason.COMMERCE,
            payments__metadata__seed="makolo-beta",
        ).distinct().count(),
        "t33_sandbox_payments": Payment.objects.filter(
            obligation__source_key="beta:t33:opportunity-fee:sandbox",
            status=PaymentStatus.SUCCEEDED,
        ).count(),
        "t33_external_evidence": PaymentEvidence.objects.filter(
            obligation__source_key="beta:t33:opportunity-fee:external",
            status=PaymentEvidenceStatus.VERIFIED,
        ).count(),
        "t33_submissions": ServiceSubmission.objects.filter(context=submission_context).count() if submission_context else 0,
        "t33_outcomes": ServiceOutcomeEvent.objects.filter(context=submission_context).count() if submission_context else 0,
    }
