from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Prefetch

from activities.models import ActivityStatus, ActivityVisibility
from journeys.models import Journey

from .models import (
    FulfillmentTargetRule,
    ObtentionConfiguration,
    ObtentionConfigurationStatus,
    ObtentionDetails,
    ObtentionJourneyContext,
    ObtentionTargetReceipt,
)


@dataclass(frozen=True)
class TargetFulfillment:
    target: object
    received_quantity: Decimal
    quantity_satisfied: bool
    beneficiary_confirmed: bool
    operator_confirmed: bool
    satisfied: bool


@dataclass(frozen=True)
class ObtentionFulfillment:
    configuration: ObtentionConfiguration
    targets: tuple[TargetFulfillment, ...]
    satisfied_count: int
    required_count: int
    complete: bool

    @property
    def total_count(self):
        return len(self.targets)


def published_configuration(obtention: ObtentionDetails):
    return (
        obtention.configurations.filter(status=ObtentionConfigurationStatus.PUBLISHED)
        .select_related("journey_plan_template")
        .prefetch_related(
            "targets",
            "modes",
            "journey_plan_template__steps__dependencies__depends_on",
            "requirement_links__requirement",
        )
        .first()
    )


def public_obtentions():
    return (
        ObtentionDetails.objects.select_related(
            "activity",
            "activity__space",
            "activity__owner_profile",
        )
        .filter(
            activity__status=ActivityStatus.PUBLISHED,
            activity__visibility__in=[ActivityVisibility.PUBLIC, ActivityVisibility.UNLISTED],
            configurations__status=ObtentionConfigurationStatus.PUBLISHED,
        )
        .prefetch_related(
            Prefetch(
                "configurations",
                queryset=ObtentionConfiguration.objects.filter(
                    status=ObtentionConfigurationStatus.PUBLISHED
                )
                .select_related("journey_plan_template")
                .prefetch_related(
                    "targets",
                    "modes",
                    "requirement_links__requirement",
                ),
                to_attr="published_configurations",
            )
        )
        .distinct()
    )


def obtention_journey_queryset(queryset=None):
    queryset = queryset if queryset is not None else Journey.objects.all()
    return queryset.select_related(
        "activity",
        "activity__space",
        "activity__owner_profile",
        "obtention_context",
        "obtention_context__configuration",
        "obtention_context__configuration__obtention",
        "obtention_context__mode",
    ).prefetch_related(
        "obtention_context__configuration__targets",
        "obtention_target_receipts",
        "steps__assignments",
        "requirement_assessments__requirement",
        "requirement_assessments__journey_step",
        "assignments",
    )


def fulfillment_for_journey(journey) -> ObtentionFulfillment:
    try:
        context = journey.obtention_context
    except ObtentionJourneyContext.DoesNotExist as exc:
        raise ValueError("Cette Journey n'est pas une Journey Obtention.") from exc

    configuration = context.configuration
    targets = list(configuration.targets.all())
    receipts = {
        row.target_id: row
        for row in journey.obtention_target_receipts.all()
    }
    rows = []
    for target in targets:
        receipt = receipts.get(target.pk)
        received = receipt.received_quantity if receipt else Decimal("0")
        quantity_satisfied = received >= target.quantity
        beneficiary_confirmed = bool(receipt and receipt.beneficiary_confirmed_at)
        operator_confirmed = bool(receipt and receipt.operator_confirmed_at)
        satisfied = (
            quantity_satisfied
            and (
                not configuration.beneficiary_confirmation_required
                or beneficiary_confirmed
            )
            and (
                not configuration.operator_confirmation_required
                or operator_confirmed
            )
        )
        rows.append(
            TargetFulfillment(
                target=target,
                received_quantity=received,
                quantity_satisfied=quantity_satisfied,
                beneficiary_confirmed=beneficiary_confirmed,
                operator_confirmed=operator_confirmed,
                satisfied=satisfied,
            )
        )

    satisfied_count = sum(1 for row in rows if row.satisfied)
    if configuration.target_rule == FulfillmentTargetRule.ALL:
        required_count = len(rows)
    elif configuration.target_rule == FulfillmentTargetRule.ANY:
        required_count = 1
    else:
        required_count = configuration.minimum_targets or 0
    complete = bool(rows) and satisfied_count >= required_count
    return ObtentionFulfillment(
        configuration=configuration,
        targets=tuple(rows),
        satisfied_count=satisfied_count,
        required_count=required_count,
        complete=complete,
    )
