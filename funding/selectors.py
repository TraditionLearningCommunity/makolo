from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from activities.models import ActivityStatus, ActivityVisibility
from payments.models import PaymentObligationStatus

from .models import FundingContribution, FundingDetails


@dataclass(frozen=True)
class FundingProgress:
    currency: str
    raised_amount: Decimal
    target_amount: Decimal | None
    remaining_amount: Decimal | None
    exceeded_amount: Decimal | None
    target_reached: bool
    percent_reached: Decimal | None


def funding_progress(funding: FundingDetails) -> FundingProgress:
    raised = FundingContribution.objects.filter(
        funding=funding,
        payment_obligation__status=PaymentObligationStatus.SATISFIED,
    ).aggregate(
        total=Coalesce(Sum("amount"), Decimal("0.00")),
    )["total"]
    target = funding.target_amount
    if target is None:
        return FundingProgress(
            currency=funding.currency,
            raised_amount=raised,
            target_amount=None,
            remaining_amount=None,
            exceeded_amount=None,
            target_reached=False,
            percent_reached=None,
        )
    remaining = max(target - raised, Decimal("0.00"))
    exceeded = max(raised - target, Decimal("0.00"))
    percent = (raised / target * Decimal("100")) if target else None
    return FundingProgress(
        currency=funding.currency,
        raised_amount=raised,
        target_amount=target,
        remaining_amount=remaining,
        exceeded_amount=exceeded,
        target_reached=raised >= target,
        percent_reached=percent,
    )


def funding_accepts_contributions(funding: FundingDetails, *, at=None) -> bool:
    at = at or timezone.now()
    activity = funding.activity
    if activity.status != ActivityStatus.PUBLISHED:
        return False
    if activity.visibility == ActivityVisibility.PRIVATE:
        return False
    if funding.opens_at and at < funding.opens_at:
        return False
    if funding.closes_at and at >= funding.closes_at:
        return False
    return True


def public_fundings(*, at=None):
    at = at or timezone.now()
    return (
        FundingDetails.objects.filter(
            activity__status=ActivityStatus.PUBLISHED,
            activity__visibility=ActivityVisibility.PUBLIC,
        )
        .filter(models_window_q(at))
        .select_related("activity", "activity__space", "activity__owner_profile")
        .order_by("activity__title", "id")
    )


def models_window_q(at):
    from django.db.models import Q

    return (Q(opens_at__isnull=True) | Q(opens_at__lte=at)) & (Q(closes_at__isnull=True) | Q(closes_at__gt=at))
