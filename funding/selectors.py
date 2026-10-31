from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from accounts.models import UserProfile
from activities.models import ActivityStatus, ActivityVisibility
from organizations.models import SpaceLifecycle
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


def _funding_progress_from_raised(
    funding: FundingDetails,
    raised: Decimal,
) -> FundingProgress:
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


def funding_progress(funding: FundingDetails) -> FundingProgress:
    raised = FundingContribution.objects.filter(
        funding=funding,
        payment_obligation__status=PaymentObligationStatus.SATISFIED,
    ).aggregate(
        total=Coalesce(Sum("amount"), Decimal("0.00")),
    )["total"]
    return _funding_progress_from_raised(funding, raised)


def funding_progress_many(fundings) -> dict:
    fundings = list(fundings)
    if not fundings:
        return {}
    ids = [funding.pk for funding in fundings]
    raised_by_id = {
        row["funding_id"]: row["total"]
        for row in FundingContribution.objects.filter(
            funding_id__in=ids,
            payment_obligation__status=PaymentObligationStatus.SATISFIED,
        )
        .values("funding_id")
        .annotate(total=Sum("amount"))
    }
    zero = Decimal("0.00")
    return {
        funding.pk: _funding_progress_from_raised(
            funding,
            raised_by_id.get(funding.pk, zero),
        )
        for funding in fundings
    }


def funding_accepts_contributions(funding: FundingDetails, *, at=None) -> bool:
    at = at or timezone.now()
    activity = funding.activity
    if activity.status != ActivityStatus.PUBLISHED:
        return False
    if activity.visibility == ActivityVisibility.PRIVATE:
        return False
    # Suspension of a Space is a current owner restriction, not an archived
    # Discovery snapshot. Never create a new payment obligation while its
    # economic owner is unable to operate.
    if activity.space_id is not None:
        space = activity.space
        if (
            not space.public_profile
            or not space.searchable
            or space.lifecycle != SpaceLifecycle.ACTIVE
            or space.verification_status == "suspended"
        ):
            return False
    elif activity.owner_profile_id is None or not activity.owner_profile.is_active:
        return False
    else:
        # A Profile can explicitly withdraw its public visibility even when
        # a legacy published Activity still exists. Missing extension rows
        # retain the previous Activity-public behavior until onboarding.
        privacy = UserProfile.objects.filter(
            user_id=activity.owner_profile_id,
        ).values("public_profile", "searchable").first()
        if privacy is not None and (
            not privacy["public_profile"] or not privacy["searchable"]
        ):
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
        # Discovery is a public catalog: a suspended/archived/non-public
        # Space cannot publish Funding into it. Personal Activities must have
        # an active logical Profile owner. Group eligibility is applied by
        # the caller after this owner-level publication gate.
        .filter(
            Q(
                activity__space__isnull=False,
                activity__space__public_profile=True,
                activity__space__searchable=True,
                activity__space__lifecycle=SpaceLifecycle.ACTIVE,
            )
            | (
                Q(
                    activity__space__isnull=True,
                    activity__owner_profile__is_active=True,
                )
                & (
                    Q(activity__owner_profile__profile__isnull=True)
                    | Q(
                        activity__owner_profile__profile__public_profile=True,
                        activity__owner_profile__profile__searchable=True,
                    )
                )
            )
        )
        .exclude(activity__space__verification_status="suspended")
        .filter(models_window_q(at))
        .select_related("activity", "activity__space", "activity__owner_profile")
        .order_by("activity__title", "id")
    )


def models_window_q(at):
    from django.db.models import Q

    return (Q(opens_at__isnull=True) | Q(opens_at__lte=at)) & (Q(closes_at__isnull=True) | Q(closes_at__gt=at))
