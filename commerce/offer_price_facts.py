"""Owner-level price facts for read models; not a checkout quotation.

The caller resolves the Activity/Occurrence visibility and authorization. This
selector never infers a zero price from a missing Offer and never combines
currencies or computes taxes/processing charges.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Count, Max, Min
from django.utils import timezone

from .selectors import currently_available_offers


def _amount_as_text(amount: Decimal | None) -> str | None:
    """Serialize owner Offer unit prices with stable two-decimal precision."""
    return format(amount, ".2f") if amount is not None else None


@dataclass(frozen=True)
class OfferPriceFacts:
    state: str
    minimum: Decimal | None
    maximum: Decimal | None
    currency: str | None
    offer_count: int
    reason: str | None
    owner_updated_at: object | None
    earliest_offer_end_at: object | None

    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "minimum": _amount_as_text(self.minimum),
            "maximum": _amount_as_text(self.maximum),
            "currency": self.currency,
            "offer_count": self.offer_count,
            "reason": self.reason,
            "basis": "active_offers_in_time_window",
            "owner_updated_at": (
                self.owner_updated_at.isoformat()
                if self.owner_updated_at is not None else None
            ),
            "earliest_offer_end_at": (
                self.earliest_offer_end_at.isoformat()
                if self.earliest_offer_end_at is not None else None
            ),
            # The owner record's update time is not a check of real-world
            # price, capacity, taxes, discounts or payment readiness.
            "fact_freshness": "not_asserted",
        }


def offer_price_facts(*, activity=None, occurrence=None, at=None) -> OfferPriceFacts:
    """Summarize prices the Commerce owner can establish in one context.

    For an Activity alone, only Activity-scoped Offers are applicable.
    With an Occurrence, its specific Offers and genuinely shared Activity
    Offers may apply. Distinct Occurrence variants should be evaluated per
    Occurrence rather than silently folded into a fictional Activity price.

    Results are indicative unit prices, not a checkout quote or a claim of
    capacity. Commerce order services remain authoritative for totals.
    """
    if (activity is None) == (occurrence is None):
        raise ValueError("Précisez exactement une Activity ou une Occurrence.")
    now = at if at is not None else timezone.now()
    offers = currently_available_offers(
        activity=activity, occurrence=occurrence, now=now
    )
    stats = offers.aggregate(
        offer_count=Count("id"),
        currency_count=Count("currency", distinct=True),
        minimum=Min("unit_price"),
        maximum=Max("unit_price"),
        owner_updated_at=Max("updated_at"),
        earliest_offer_end_at=Min("available_until"),
    )
    count = stats["offer_count"]
    if count == 0 or stats["currency_count"] != 1:
        return OfferPriceFacts(
            state="unknown", minimum=None, maximum=None, currency=None,
            offer_count=count,
            reason="no_applicable_offer" if count == 0 else "mixed_currencies",
            owner_updated_at=stats["owner_updated_at"],
            earliest_offer_end_at=stats["earliest_offer_end_at"],
        )

    currency = offers.values_list("currency", flat=True).first()
    minimum = stats["minimum"]
    maximum = stats["maximum"]
    if maximum == Decimal("0.00"):
        state = "free"
    elif minimum == maximum:
        state = "exact"
    else:
        state = "range"
    return OfferPriceFacts(
        state=state, minimum=minimum, maximum=maximum,
        currency=currency, offer_count=count, reason=None,
        owner_updated_at=stats["owner_updated_at"],
        earliest_offer_end_at=stats["earliest_offer_end_at"],
    )


def occurrence_variant_price_facts(*, occurrences, at=None) -> dict:
    """Compare at most 12 owner-scoped Occurrences selected by the caller.

    The caller MUST pass Occurrences whose visibility and viewer eligibility
    have already been checked. This is an on-demand owner read operation, not
    a public ID-based comparison API and not a replacement for checkout.
    """
    selected = list(occurrences)
    if not 2 <= len(selected) <= 12:
        raise ValueError("La comparaison exige entre 2 et 12 Occurrences.")
    identities = {occurrence.pk for occurrence in selected}
    activity_ids = {occurrence.activity_id for occurrence in selected}
    if (
        len(identities) != len(selected)
        or len(activity_ids) != 1
        or None in identities
    ):
        raise ValueError("Les variantes doivent être distinctes et partager une Activity.")

    snapshot_at = at if at is not None else timezone.now()
    rows = [
        (
            occurrence,
            offer_price_facts(occurrence=occurrence, at=snapshot_at),
        )
        for occurrence in selected
    ]
    prices = [price for _, price in rows]
    currencies = {price.currency for price in prices}
    comparable = (
        len(currencies) == 1 and None not in currencies
        and all(price.state in {"free", "exact", "range"} for price in prices)
    )
    if comparable:
        minimum = min(price.minimum for price in prices)
        maximum = max(price.maximum for price in prices)
        distinct_terms = {(price.minimum, price.maximum) for price in prices}
        if len(distinct_terms) > 1:
            state = "variant_dependent"
        elif maximum == Decimal("0.00"):
            state = "free"
        elif minimum == maximum:
            state = "exact"
        else:
            state = "range"
        currency = prices[0].currency
    else:
        state = "unknown"
        minimum = maximum = currency = None
    return {
        "state": state,
        "minimum": _amount_as_text(minimum),
        "maximum": _amount_as_text(maximum),
        "currency": currency,
        "basis": "selected_occurrence_offers",
        "fact_freshness": "not_asserted",
        "variants": [
            {
                "occurrence": {"kind": "occurrence", "id": str(occurrence.pk)},
                "price": price.as_dict(),
            }
            for occurrence, price in rows
        ],
    }



def offer_price_facts_many(*, contexts, at=None) -> dict:
    """Batch owner price facts for admitted (Activity, optional Occurrence) pairs.

    Contexts are trusted only after a caller has enforced visibility. This
    preserves applicable_offers semantics and does not assert Capacity or
    checkout totals. Unlike repeated offer_price_facts calls, it uses one
    query for the selected page.
    """
    from django.db.models import Q

    from .models import Offer, OfferStatus

    selected = {
        (str(activity_id), str(occurrence_id) if occurrence_id else None)
        for activity_id, occurrence_id in contexts
    }
    if not selected:
        return {}
    activity_ids = {activity_id for activity_id, _ in selected}
    now = at if at is not None else timezone.now()
    offers = list(
        Offer.objects.filter(
            activity_id__in=activity_ids,
            status=OfferStatus.ACTIVE,
        ).filter(
            Q(available_from__isnull=True) | Q(available_from__lte=now),
            Q(available_until__isnull=True) | Q(available_until__gt=now),
        ).select_related("capacity_pool")
    )
    by_activity = {}
    for offer in offers:
        by_activity.setdefault(str(offer.activity_id), []).append(offer)

    result = {}
    for activity_id, occurrence_id in selected:
        applicable = [
            offer
            for offer in by_activity.get(activity_id, ())
            if (
                offer.occurrence_id is None
                or (occurrence_id is not None and str(offer.occurrence_id) == occurrence_id)
            )
            and (
                offer.capacity_pool_id is None
                or offer.capacity_pool.occurrence_id is None
                or (
                    occurrence_id is not None
                    and str(offer.capacity_pool.occurrence_id) == occurrence_id
                )
            )
        ]
        currencies = {offer.currency for offer in applicable}
        minimum = maximum = currency = None
        reason = None
        if not applicable:
            state = "unknown"
            reason = "no_applicable_offer"
        elif len(currencies) != 1:
            state = "unknown"
            reason = "mixed_currencies"
        else:
            currency = next(iter(currencies))
            minimum = min(offer.unit_price for offer in applicable)
            maximum = max(offer.unit_price for offer in applicable)
            state = (
                "free" if maximum == Decimal("0.00")
                else "exact" if minimum == maximum
                else "range"
            )
        timestamps = [offer.updated_at for offer in applicable if offer.updated_at]
        ends = [offer.available_until for offer in applicable if offer.available_until]
        result[(activity_id, occurrence_id)] = OfferPriceFacts(
            state=state,
            minimum=minimum,
            maximum=maximum,
            currency=currency,
            offer_count=len(applicable),
            reason=reason,
            owner_updated_at=max(timestamps) if timestamps else None,
            earliest_offer_end_at=min(ends) if ends else None,
        )
    return result
