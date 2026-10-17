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
            "minimum": str(self.minimum) if self.minimum is not None else None,
            "maximum": str(self.maximum) if self.maximum is not None else None,
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
