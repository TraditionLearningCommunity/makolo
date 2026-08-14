from django.db.models import Q
from django.utils import timezone

from .canonical_models import PromotionOffer, PromotionTargeting
from .canonical_services import audience_allows
from .models import Promotion, PromotionCode


def valid_promotions_now(queryset=None, *, now=None):
    now = now or timezone.now()
    queryset = queryset if queryset is not None else Promotion.objects.all()
    return queryset.filter(is_active=True).filter(
        Q(starts_at__isnull=True) | Q(starts_at__lte=now),
        Q(ends_at__isnull=True) | Q(ends_at__gte=now),
    )


def active_promotions_for_space(organization, *, now=None):
    return valid_promotions_now(
        Promotion.objects.filter(organization=organization),
        now=now,
    ).order_by("name")


def promotions_for_offer(offer, *, now=None):
    explicit_ids = PromotionOffer.objects.filter(offer=offer).values_list("promotion_id", flat=True)
    implicit_ids = PromotionTargeting.objects.filter(
        Q(activity__isnull=True) | Q(activity=offer.activity),
        promotion__organization_id=offer.activity.space_id,
        promotion__offer_targets__isnull=True,
    ).values_list("promotion_id", flat=True)
    return valid_promotions_now(
        Promotion.objects.filter(Q(pk__in=explicit_ids) | Q(pk__in=implicit_ids)).distinct(),
        now=now,
    ).order_by("name")


def promotion_code_by_value(code_value, *, now=None):
    normalized = (code_value or "").strip().upper()
    if not normalized:
        return None
    now = now or timezone.now()
    return (
        PromotionCode.objects.select_related("promotion", "promotion__organization")
        .filter(code=normalized, is_active=True, promotion__is_active=True)
        .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        .filter(Q(promotion__starts_at__isnull=True) | Q(promotion__starts_at__lte=now))
        .filter(Q(promotion__ends_at__isnull=True) | Q(promotion__ends_at__gte=now))
        .first()
    )


def promotion_is_eligible_for_profile(promotion, profile):
    return audience_allows(promotion, profile)
