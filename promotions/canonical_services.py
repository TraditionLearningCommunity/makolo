from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from crm.canonical_selectors import profile_in_audience

from .canonical_models import CommercePromotionRedemption, PromotionOffer, PromotionTargeting
from .models import DiscountType, Promotion, PromotionCode, PromotionRedemption, RedemptionStatus


ACTIVE_REDEMPTION_STATUSES = [RedemptionStatus.RESERVED, RedemptionStatus.CONFIRMED]
MONEY_QUANTUM = Decimal("0.01")


def money(value):
    return Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def calculate_discount(*, eligible_amount, subtotal_amount, promotion):
    eligible_amount = money(eligible_amount)
    subtotal_amount = money(subtotal_amount)
    if promotion.discount_type == DiscountType.PERCENT:
        discount = money(eligible_amount * promotion.discount_value / Decimal("100"))
        if promotion.max_discount_amount is not None:
            discount = min(discount, promotion.max_discount_amount)
    else:
        discount = min(money(promotion.discount_value), eligible_amount)
    return max(Decimal("0.00"), min(money(discount), subtotal_amount))


def _validate_window(starts_at, ends_at, *, now, label):
    if starts_at and now < starts_at:
        raise ValidationError(f"{label} n'est pas encore actif.")
    if ends_at and now > ends_at:
        raise ValidationError(f"{label} a expiré.")


def _counts(queryset_legacy, queryset_commerce):
    return queryset_legacy.count() + queryset_commerce.count()


def promotion_usage_count(promotion):
    return _counts(
        PromotionRedemption.objects.filter(promotion=promotion, status__in=ACTIVE_REDEMPTION_STATUSES),
        CommercePromotionRedemption.objects.filter(promotion=promotion, status__in=ACTIVE_REDEMPTION_STATUSES),
    )


def code_usage_count(code):
    return _counts(
        PromotionRedemption.objects.filter(code=code, status__in=ACTIVE_REDEMPTION_STATUSES),
        CommercePromotionRedemption.objects.filter(code=code, status__in=ACTIVE_REDEMPTION_STATUSES),
    )


def customer_usage_count(promotion, *, buyer=None, customer_email=""):
    legacy = PromotionRedemption.objects.filter(promotion=promotion, status__in=ACTIVE_REDEMPTION_STATUSES)
    commerce = CommercePromotionRedemption.objects.filter(promotion=promotion, status__in=ACTIVE_REDEMPTION_STATUSES)
    if buyer is not None and getattr(buyer, "is_authenticated", False):
        return _counts(legacy.filter(buyer=buyer), commerce.filter(buyer=buyer))
    email = (customer_email or "").strip()
    return _counts(legacy.filter(customer_email__iexact=email), commerce.filter(customer_email__iexact=email))


def audience_allows(promotion, profile):
    targeting = PromotionTargeting.objects.select_related("audience").filter(promotion=promotion).first()
    if not targeting or not targeting.audience_id:
        return True
    if profile is None or not getattr(profile, "is_authenticated", False):
        return False
    return profile_in_audience(audience=targeting.audience, profile=profile)


def validate_shared_limits(*, promotion, code, buyer, customer_email):
    if promotion.max_redemptions is not None and promotion_usage_count(promotion) >= promotion.max_redemptions:
        raise ValidationError("Le quota de cette offre est épuisé.")
    if code.max_redemptions is not None and code_usage_count(code) >= code.max_redemptions:
        raise ValidationError("Le quota de ce code est épuisé.")
    if customer_usage_count(promotion, buyer=buyer, customer_email=customer_email) >= promotion.max_redemptions_per_customer:
        raise ValidationError("Vous avez déjà utilisé cette offre le nombre maximum de fois autorisé.")


def validate_audience_eligibility(*, promotion, profile):
    if not audience_allows(promotion, profile):
        raise ValidationError("Ce code promotionnel est réservé à une Audience dont vous ne faites pas partie.")


@transaction.atomic
def quote_commerce_promotion(
    *,
    code_value,
    buyer,
    customer_email,
    selections,
    subtotal_amount,
    currency,
    payee_space,
    now=None,
):
    normalized_code = (code_value or "").strip().upper()
    if not normalized_code:
        return None
    now = now or timezone.now()
    code = (
        PromotionCode.objects.select_for_update()
        .select_related("promotion", "promotion__organization")
        .filter(code=normalized_code)
        .first()
    )
    if not code:
        raise ValidationError("Code promotionnel invalide.")
    promotion = Promotion.objects.select_for_update().get(pk=code.promotion_id)
    if not code.is_active or not promotion.is_active:
        raise ValidationError("Ce code promotionnel n'est pas actif.")
    if promotion.organization_id != payee_space.pk:
        raise ValidationError("Ce code promotionnel n'est pas valable pour cet Espace.")

    _validate_window(promotion.starts_at, promotion.ends_at, now=now, label="Cette offre")
    _validate_window(code.starts_at, code.ends_at, now=now, label="Ce code")
    validate_audience_eligibility(promotion=promotion, profile=buyer)

    currency = (currency or "").strip().upper()
    if promotion.currency and promotion.currency != currency:
        raise ValidationError(f"Cette offre est réservée aux commandes en {promotion.currency}.")
    subtotal_amount = money(subtotal_amount)
    if subtotal_amount < promotion.min_order_amount:
        raise ValidationError(
            f"Cette offre nécessite une commande d'au moins {promotion.min_order_amount} {currency}."
        )
    validate_shared_limits(
        promotion=promotion,
        code=code,
        buyer=buyer,
        customer_email=customer_email,
    )

    targeting = PromotionTargeting.objects.select_related("activity").filter(promotion=promotion).first()
    offer_target_ids = set(PromotionOffer.objects.filter(promotion=promotion).values_list("offer_id", flat=True))
    eligible_amount = Decimal("0.00")
    eligible_offer_ids = set()
    for offer, quantity in selections:
        if offer.activity.space_id != promotion.organization_id:
            continue
        if targeting and targeting.activity_id and offer.activity_id != targeting.activity_id:
            continue
        if offer_target_ids and offer.pk not in offer_target_ids:
            continue
        eligible_offer_ids.add(offer.pk)
        eligible_amount += offer.unit_price * quantity
    eligible_amount = money(eligible_amount)
    if eligible_amount <= 0:
        raise ValidationError("Aucune Offer sélectionnée n'est éligible à cette Promotion.")

    discount_amount = calculate_discount(
        eligible_amount=eligible_amount,
        subtotal_amount=subtotal_amount,
        promotion=promotion,
    )
    if discount_amount <= 0:
        raise ValidationError("Cette offre ne produit aucune remise sur la sélection actuelle.")
    return {
        "promotion": promotion,
        "code": code,
        "subtotal_amount": subtotal_amount,
        "eligible_amount": eligible_amount,
        "discount_amount": discount_amount,
        "final_amount": money(subtotal_amount - discount_amount),
        "currency": currency,
        "eligible_offer_ids": eligible_offer_ids,
    }


def allocate_discount(*, prepared, quote):
    if not quote:
        return [(offer, quantity, beneficiary, subtotal, Decimal("0.00")) for offer, quantity, beneficiary, subtotal, _discount in prepared]
    remaining = quote["discount_amount"]
    eligible_ids = quote["eligible_offer_ids"]
    eligible_lines = [row for row in prepared if row[0].pk in eligible_ids]
    result = []
    for row in prepared:
        offer, quantity, beneficiary, subtotal, _client_discount = row
        discount = Decimal("0.00")
        if offer.pk in eligible_ids and eligible_lines:
            if row is eligible_lines[-1]:
                discount = min(remaining, subtotal)
            else:
                proportion = subtotal / quote["eligible_amount"] if quote["eligible_amount"] else Decimal("0.00")
                discount = min(money(quote["discount_amount"] * proportion), subtotal, remaining)
            remaining = money(remaining - discount)
        result.append((offer, quantity, beneficiary, subtotal, discount))
    return result


def create_commerce_redemption(*, order, quote):
    if not quote:
        return None
    return CommercePromotionRedemption.objects.create(
        promotion=quote["promotion"],
        code=quote["code"],
        commerce_order=order,
        buyer=order.buyer,
        customer_email=(getattr(order.buyer, "email", "") or ""),
        status=RedemptionStatus.RESERVED,
        subtotal_amount=quote["subtotal_amount"],
        eligible_amount=quote["eligible_amount"],
        discount_amount=quote["discount_amount"],
        final_amount=quote["final_amount"],
        currency=quote["currency"],
    )


@transaction.atomic
def confirm_commerce_redemption(*, order):
    redemption = CommercePromotionRedemption.objects.select_for_update().filter(commerce_order=order).first()
    if not redemption or redemption.status == RedemptionStatus.REVERSED:
        return redemption
    if redemption.status != RedemptionStatus.CONFIRMED:
        redemption.status = RedemptionStatus.CONFIRMED
        redemption.confirmed_at = redemption.confirmed_at or timezone.now()
        redemption.save(update_fields=["status", "confirmed_at"])
    return redemption


@transaction.atomic
def reverse_commerce_redemption(*, order):
    redemption = CommercePromotionRedemption.objects.select_for_update().filter(commerce_order=order).first()
    if not redemption or redemption.status == RedemptionStatus.REVERSED:
        return redemption
    redemption.status = RedemptionStatus.REVERSED
    redemption.reversed_at = timezone.now()
    redemption.save(update_fields=["status", "reversed_at"])
    return redemption
