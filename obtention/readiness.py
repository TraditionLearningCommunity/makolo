from journeys.models import JourneyStatus
from readiness.registry import registry
from readiness.types import NextAction, ReadinessCheck, ReadinessCheckState

from .models import ObtentionJourneyContext
from .selectors import fulfillment_for_journey


@registry.register
def obtention_fulfillment_contributor(journey, viewer, now):
    try:
        journey.obtention_context
    except ObtentionJourneyContext.DoesNotExist:
        return []

    result = fulfillment_for_journey(journey)
    if result.complete:
        return [
            ReadinessCheck(
                key="obtention.fulfillment",
                source="obtention",
                state=ReadinessCheckState.SATISFIED,
                blocking=False,
                reason_code="obtention_fulfillment_satisfied",
                summary=result.configuration.result_label,
            )
        ]

    if journey.status not in {JourneyStatus.CONFIRMED, JourneyStatus.IN_PROGRESS}:
        return [
            ReadinessCheck(
                key="obtention.fulfillment",
                source="obtention",
                state=ReadinessCheckState.WAITING,
                blocking=False,
                reason_code="obtention_journey_not_confirmed",
                summary="L'accomplissement sera vérifié lorsque la démarche sera confirmée.",
            )
        ]

    checks = []
    beneficiary_id = journey.beneficiary_id
    for row in result.targets:
        if row.satisfied:
            continue
        missing_operator = (
            result.configuration.operator_confirmation_required
            and not row.operator_confirmed
        )
        missing_beneficiary = (
            result.configuration.beneficiary_confirmation_required
            and not row.beneficiary_confirmed
        )
        missing_quantity = not row.quantity_satisfied

        if missing_operator and not (missing_quantity or missing_beneficiary):
            checks.append(
                ReadinessCheck(
                    key=f"obtention.target.{row.target.pk}",
                    source="obtention",
                    state=ReadinessCheckState.WAITING,
                    blocking=False,
                    reason_code="obtention_operator_confirmation_pending",
                    summary=f"Validation du porteur attendue : {row.target.title}",
                )
            )
            continue

        action = None
        state = ReadinessCheckState.WAITING
        reason = "obtention_receipt_pending"
        if viewer is None or getattr(viewer, "pk", None) == beneficiary_id:
            state = ReadinessCheckState.ACTION_REQUIRED
            reason = "obtention_beneficiary_confirmation_required"
            action = NextAction(
                key="confirm_obtention_receipt",
                label=f"Confirmer : {row.target.title}",
                url=f"/obtention/journeys/{journey.pk}/",
                source="obtention",
            )
        checks.append(
            ReadinessCheck(
                key=f"obtention.target.{row.target.pk}",
                source="obtention",
                state=state,
                blocking=False,
                reason_code=reason,
                summary=row.target.title,
                next_action=action,
            )
        )

    if not checks:
        checks.append(
            ReadinessCheck(
                key="obtention.fulfillment",
                source="obtention",
                state=ReadinessCheckState.WAITING,
                blocking=False,
                reason_code="obtention_fulfillment_pending",
                summary=result.configuration.result_label,
            )
        )
    return checks
