from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.utils import timezone

from .models import DiscountType, Promotion, PromotionCode, PromotionRedemption, RedemptionStatus
from .permissions import user_can_manage_promotions


ACTIVE_REDEMPTION_STATUSES = [RedemptionStatus.RESERVED, RedemptionStatus.CONFIRMED]
MONEY_QUANTUM = Decimal("0.01")


def _money(value):
    return Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _validate_window(*, starts_at, ends_at, now, label):
    if starts_at and now < starts_at:
        raise ValidationError(f"{label} n'est pas encore actif.")
    if ends_at and now > ends_at:
        raise ValidationError(f"{label} a expiré.")


def _customer_redemption_count(promotion, *, buyer=None, customer_email=""):
    from .canonical_services import customer_usage_count
    return customer_usage_count(promotion, buyer=buyer, customer_email=customer_email)


def quote_promotion(
    *,
    code_value,
    event,
    buyer,
    customer_email,
    selections,
    subtotal_amount,
    currency,
    now=None,
):
    """Valide et verrouille un code dans la transaction d'achat Event.

    `selections` contient des tuples `(TicketType, quantité)`. Le verrou sur le
    code/promotion reste détenu jusqu'à la fin de `create_order`, ce qui rend les
    quotas cohérents lorsque la base supporte les verrous de lignes. Les quotas
    et l'éligibilité Audience sont partagés avec le checkout Commerce canonique.
    """
    from .canonical_services import code_usage_count, promotion_usage_count, validate_audience_eligibility

    normalized_code = (code_value or "").strip().upper()
    if not normalized_code:
        return None

    now = now or timezone.now()
    code = (
        PromotionCode.objects.select_for_update()
        .select_related("promotion", "promotion__organization", "promotion__event", "crm_campaign")
        .filter(code=normalized_code)
        .first()
    )
    if not code:
        raise ValidationError("Code promotionnel invalide.")
    promotion = Promotion.objects.select_for_update().get(pk=code.promotion_id)

    if not code.is_active or not promotion.is_active:
        raise ValidationError("Ce code promotionnel n'est pas actif.")
    if event.organization_id != promotion.organization_id:
        raise ValidationError("Ce code promotionnel n'est pas valable pour cet organisateur.")
    if promotion.event_id and promotion.event_id != event.pk:
        raise ValidationError("Ce code promotionnel n'est pas valable pour cet événement.")

    _validate_window(starts_at=promotion.starts_at, ends_at=promotion.ends_at, now=now, label="Cette offre")
    _validate_window(starts_at=code.starts_at, ends_at=code.ends_at, now=now, label="Ce code")
    validate_audience_eligibility(promotion=promotion, profile=buyer)

    currency = (currency or "").upper()
    if promotion.currency and promotion.currency != currency:
        raise ValidationError(f"Cette offre est réservée aux commandes en {promotion.currency}.")
    subtotal_amount = _money(subtotal_amount)
    if subtotal_amount < promotion.min_order_amount:
        raise ValidationError(
            f"Cette offre nécessite une commande d'au moins {promotion.min_order_amount} {currency}."
        )

    if promotion.max_redemptions is not None and promotion_usage_count(promotion) >= promotion.max_redemptions:
        raise ValidationError("Le quota de cette offre est épuisé.")
    if code.max_redemptions is not None and code_usage_count(code) >= code.max_redemptions:
        raise ValidationError("Le quota de ce code est épuisé.")
    if _customer_redemption_count(
        promotion,
        buyer=buyer,
        customer_email=customer_email,
    ) >= promotion.max_redemptions_per_customer:
        raise ValidationError("Vous avez déjà utilisé cette offre le nombre maximum de fois autorisé.")

    eligible_ids = set(promotion.eligible_ticket_types.values_list("pk", flat=True))
    eligible_amount = Decimal("0.00")
    for ticket_type, quantity in selections:
        if eligible_ids and ticket_type.pk not in eligible_ids:
            continue
        eligible_amount += ticket_type.price * quantity
    eligible_amount = _money(eligible_amount)
    if eligible_amount <= 0:
        raise ValidationError("Aucun billet sélectionné n'est éligible à cette offre.")

    if promotion.discount_type == DiscountType.PERCENT:
        discount_amount = _money(eligible_amount * promotion.discount_value / Decimal("100"))
        if promotion.max_discount_amount is not None:
            discount_amount = min(discount_amount, promotion.max_discount_amount)
    else:
        discount_amount = min(_money(promotion.discount_value), eligible_amount)

    discount_amount = min(discount_amount, subtotal_amount)
    if discount_amount <= 0:
        raise ValidationError("Cette offre ne produit aucune remise sur la sélection actuelle.")

    return {
        "promotion": promotion,
        "code": code,
        "subtotal_amount": subtotal_amount,
        "eligible_amount": eligible_amount,
        "discount_amount": discount_amount,
        "final_amount": _money(subtotal_amount - discount_amount),
        "currency": currency,
    }


def create_redemption(*, order, quote):
    if not quote:
        return None
    return PromotionRedemption.objects.create(
        promotion=quote["promotion"],
        code=quote["code"],
        order=order,
        buyer=order.buyer,
        customer_email=order.customer_email,
        status=(RedemptionStatus.CONFIRMED if order.status == "confirmed" else RedemptionStatus.RESERVED),
        subtotal_amount=quote["subtotal_amount"],
        eligible_amount=quote["eligible_amount"],
        discount_amount=quote["discount_amount"],
        final_amount=quote["final_amount"],
        currency=quote["currency"],
        confirmed_at=timezone.now() if order.status == "confirmed" else None,
    )


@transaction.atomic
def confirm_redemption(*, order):
    redemption = PromotionRedemption.objects.select_for_update().filter(order=order).first()
    if not redemption or redemption.status == RedemptionStatus.REVERSED:
        return redemption
    if order.status != "confirmed":
        return redemption
    if redemption.status != RedemptionStatus.CONFIRMED:
        redemption.status = RedemptionStatus.CONFIRMED
        redemption.confirmed_at = redemption.confirmed_at or timezone.now()
        redemption.save(update_fields=["status", "confirmed_at"])
    return redemption


@transaction.atomic
def reverse_redemption(*, order):
    redemption = PromotionRedemption.objects.select_for_update().filter(order=order).first()
    if not redemption or redemption.status == RedemptionStatus.REVERSED:
        return redemption
    redemption.status = RedemptionStatus.REVERSED
    redemption.reversed_at = timezone.now()
    redemption.save(update_fields=["status", "reversed_at"])
    return redemption


def public_codes_for_event(event, *, now=None):
    now = now or timezone.now()
    queryset = (
        PromotionCode.objects.select_related("promotion")
        .filter(
            is_active=True,
            is_private=False,
            promotion__is_active=True,
            promotion__organization_id=event.organization_id,
        )
        .filter(Q(promotion__event__isnull=True) | Q(promotion__event=event))
        .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=now))
        .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=now))
        .filter(Q(promotion__starts_at__isnull=True) | Q(promotion__starts_at__lte=now))
        .filter(Q(promotion__ends_at__isnull=True) | Q(promotion__ends_at__gte=now))
        .order_by("promotion__name", "code")
    )
    return queryset


def promotion_metrics(promotion, *, include_financials=False):
    redemptions = promotion.redemptions.all()
    confirmed = redemptions.filter(status=RedemptionStatus.CONFIRMED)
    metrics = {
        "reserved": redemptions.filter(status=RedemptionStatus.RESERVED).count(),
        "confirmed": confirmed.count(),
        "reversed": redemptions.filter(status=RedemptionStatus.REVERSED).count(),
        "codes": [],
    }
    for code in promotion.codes.all().order_by("code"):
        code_redemptions = code.redemptions.all()
        row = {
            "id": str(code.pk),
            "code": code.code,
            "label": code.label,
            "private": code.is_private,
            "reserved": code_redemptions.filter(status=RedemptionStatus.RESERVED).count(),
            "confirmed": code_redemptions.filter(status=RedemptionStatus.CONFIRMED).count(),
            "reversed": code_redemptions.filter(status=RedemptionStatus.REVERSED).count(),
            "crm_campaign_id": str(code.crm_campaign_id) if code.crm_campaign_id else None,
        }
        metrics["codes"].append(row)

    if include_financials:
        rows = (
            confirmed.values("currency")
            .annotate(
                discount_total=Sum("discount_amount"),
                attributed_revenue=Sum("final_amount"),
                orders=Count("id"),
            )
            .order_by("currency")
        )
        metrics["financials"] = [
            {
                "currency": row["currency"],
                "discount_total": row["discount_total"] or Decimal("0.00"),
                "attributed_revenue": row["attributed_revenue"] or Decimal("0.00"),
                "orders": row["orders"],
            }
            for row in rows
        ]
    return metrics


@transaction.atomic
def create_promotion(*, actor, organization, **data):
    if not user_can_manage_promotions(actor, organization):
        raise PermissionDenied("Vous ne pouvez pas créer d'offre pour cette organisation.")
    eligible_ticket_types = data.pop("eligible_ticket_types", [])
    promotion = Promotion(organization=organization, created_by=actor, **data)
    promotion.full_clean()
    promotion.save()
    if eligible_ticket_types:
        for ticket_type in eligible_ticket_types:
            if ticket_type.event.organization_id != organization.pk:
                raise ValidationError("Un type de billet sélectionné appartient à une autre organisation.")
            if promotion.event_id and ticket_type.event_id != promotion.event_id:
                raise ValidationError("Un type de billet sélectionné appartient à un autre événement.")
        promotion.eligible_ticket_types.set(eligible_ticket_types)
    return promotion


@transaction.atomic
def create_promotion_code(*, actor, promotion, **data):
    promotion = Promotion.objects.select_for_update().select_related("organization").get(pk=promotion.pk)
    if not user_can_manage_promotions(actor, promotion.organization):
        raise PermissionDenied("Vous ne pouvez pas créer de code pour cette offre.")
    code = PromotionCode(promotion=promotion, created_by=actor, **data)
    code.full_clean()
    code.save()
    return code


@transaction.atomic
def toggle_promotion(*, actor, promotion):
    promotion = Promotion.objects.select_for_update().select_related("organization").get(pk=promotion.pk)
    if not user_can_manage_promotions(actor, promotion.organization):
        raise PermissionDenied("Vous ne pouvez pas modifier cette offre.")
    promotion.is_active = not promotion.is_active
    promotion.save(update_fields=["is_active", "updated_at"])
    return promotion


@transaction.atomic
def toggle_promotion_code(*, actor, code):
    code = (
        PromotionCode.objects.select_for_update()
        .select_related("promotion", "promotion__organization")
        .get(pk=code.pk)
    )
    if not user_can_manage_promotions(actor, code.promotion.organization):
        raise PermissionDenied("Vous ne pouvez pas modifier ce code.")
    code.is_active = not code.is_active
    code.save(update_fields=["is_active", "updated_at"])
    return code
