from django.db.models import Q
from django.utils import timezone

from .models import CommerceOrder, Offer, OfferStatus


def offers_for_activity(activity):
    return Offer.objects.filter(activity=activity).select_related("activity", "occurrence", "capacity_pool").order_by("unit_price", "name", "id")


def offers_for_occurrence(occurrence):
    return Offer.objects.filter(occurrence=occurrence).select_related("activity", "occurrence", "capacity_pool").order_by("unit_price", "name", "id")


def offer_applies_to_occurrence(offer, occurrence) -> bool:
    """Whether an Offer can truthfully apply in this Occurrence context."""
    if offer.activity_id != occurrence.activity_id:
        return False
    if offer.occurrence_id is not None and offer.occurrence_id != occurrence.pk:
        return False
    pool = offer.capacity_pool
    if pool is not None and pool.occurrence_id is not None and pool.occurrence_id != occurrence.pk:
        return False
    return True


def applicable_offers(*, activity=None, occurrence=None):
    """Canonical read selector for Activity/Occurrence Offer applicability.

    With an Occurrence, both Activity-scoped Offers and Offers scoped to that
    exact Occurrence may apply. Activity-scoped Offers backed by a pool for a
    different Occurrence are excluded. With Activity only, only genuinely
    Activity-scoped Offers are returned.
    """
    if occurrence is not None:
        activity = occurrence.activity
        qs = Offer.objects.filter(activity=activity).filter(
            Q(occurrence__isnull=True) | Q(occurrence=occurrence),
            Q(capacity_pool__isnull=True)
            | Q(capacity_pool__occurrence__isnull=True)
            | Q(capacity_pool__occurrence=occurrence),
        )
    elif activity is not None:
        qs = Offer.objects.filter(activity=activity, occurrence__isnull=True).filter(
            Q(capacity_pool__isnull=True) | Q(capacity_pool__occurrence__isnull=True)
        )
    else:
        raise ValueError("applicable_offers exige activity ou occurrence")
    return qs.select_related("activity", "occurrence", "capacity_pool").order_by("unit_price", "name", "id")


def currently_available_offers(*, activity=None, occurrence=None, now=None):
    now = now or timezone.now()
    qs = applicable_offers(activity=activity, occurrence=occurrence).filter(
        status=OfferStatus.ACTIVE,
    ).filter(
        Q(available_from__isnull=True) | Q(available_from__lte=now),
        Q(available_until__isnull=True) | Q(available_until__gt=now),
    )
    return qs.order_by("unit_price", "name", "id")


def orders_for_profile(profile):
    return CommerceOrder.objects.filter(buyer=profile).select_related("journey", "journey__activity", "payee_space").order_by("-created_at")


def orders_for_activity(activity):
    return CommerceOrder.objects.filter(journey__activity=activity).select_related("journey", "buyer", "payee_space").order_by("-created_at")


def orders_for_space(space):
    return CommerceOrder.objects.filter(payee_space=space).select_related("journey", "journey__activity", "buyer", "payee_space").order_by("-created_at")


def order_with_items(order_id):
    return CommerceOrder.objects.select_related("journey", "journey__activity", "buyer", "payee_space").prefetch_related(
        "items__offer",
        "items__beneficiary",
        "items__capacity_reservation",
    ).get(pk=order_id)
