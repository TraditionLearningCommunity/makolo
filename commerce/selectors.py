from django.db.models import Q
from django.utils import timezone

from .models import CommerceOrder, Offer, OfferStatus


def offers_for_activity(activity):
    return Offer.objects.filter(activity=activity).select_related("activity", "occurrence", "capacity_pool").order_by("unit_price", "name", "id")


def offers_for_occurrence(occurrence):
    return Offer.objects.filter(occurrence=occurrence).select_related("activity", "occurrence", "capacity_pool").order_by("unit_price", "name", "id")


def currently_available_offers(*, activity=None, occurrence=None, now=None):
    now = now or timezone.now()
    qs = Offer.objects.filter(status=OfferStatus.ACTIVE).filter(
        Q(available_from__isnull=True) | Q(available_from__lte=now),
        Q(available_until__isnull=True) | Q(available_until__gt=now),
    )
    if activity is not None:
        qs = qs.filter(activity=activity)
    if occurrence is not None:
        qs = qs.filter(occurrence=occurrence)
    return qs.select_related("activity", "occurrence", "capacity_pool").order_by("unit_price", "name", "id")


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
