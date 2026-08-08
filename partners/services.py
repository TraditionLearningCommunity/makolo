import uuid
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from urllib.parse import urlparse

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from tickets.models import TicketOrder, TicketOrderStatus

from .models import (
    AffiliateCampaign,
    AttributionStatus,
    CampaignStatus,
    CommissionStatus,
    CommissionType,
    Partner,
    PartnerCommission,
    PartnerPayout,
    PartnerStatus,
    PayoutStatus,
    ReferralAttribution,
    ReferralCode,
    ReferralVisit,
)
from .permissions import user_can_manage_partner_payouts, user_can_manage_partners


REFERRAL_SESSION_CODE_KEY = "makolo_referral_code"
REFERRAL_SESSION_VISITOR_KEY = "makolo_referral_visitor_id"
REFERRAL_SESSION_CAPTURED_AT_KEY = "makolo_referral_captured_at"


def _quantize(value):
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _safe_referrer_domain(value: str) -> str:
    try:
        return (urlparse(value).hostname or "")[:255]
    except Exception:
        return ""


def validate_referral_code(code: str, *, event=None):
    normalized = (code or "").strip().upper()
    if not normalized:
        return None
    referral = (
        ReferralCode.objects.select_related("campaign", "campaign__event", "partner")
        .filter(code=normalized, is_active=True)
        .first()
    )
    if not referral or not referral.is_usable:
        return None
    if event is not None and referral.campaign.event_id != event.pk:
        return None
    return referral


def capture_referral_request(request, code: str):
    referral = validate_referral_code(code)
    if not referral:
        return None

    raw_visitor = request.session.get(REFERRAL_SESSION_VISITOR_KEY)
    try:
        visitor_id = uuid.UUID(str(raw_visitor)) if raw_visitor else uuid.uuid4()
    except ValueError:
        visitor_id = uuid.uuid4()

    request.session[REFERRAL_SESSION_CODE_KEY] = referral.code
    request.session[REFERRAL_SESSION_VISITOR_KEY] = str(visitor_id)
    request.session[REFERRAL_SESSION_CAPTURED_AT_KEY] = timezone.now().isoformat()

    ReferralVisit.objects.get_or_create(
        referral_code=referral,
        visitor_id=visitor_id,
        defaults={
            "landing_path": request.path[:255],
            "referrer_domain": _safe_referrer_domain(request.META.get("HTTP_REFERER", "")),
        },
    )
    return referral


def get_session_referral(request, *, event=None):
    code = request.session.get(REFERRAL_SESSION_CODE_KEY, "")
    referral = validate_referral_code(code, event=event)
    if not referral:
        return None

    captured_at_raw = request.session.get(REFERRAL_SESSION_CAPTURED_AT_KEY)
    if captured_at_raw:
        try:
            captured_at = datetime.fromisoformat(captured_at_raw)
            if timezone.is_naive(captured_at):
                captured_at = timezone.make_aware(captured_at)
            if timezone.now() > captured_at + timedelta(days=referral.campaign.attribution_window_days):
                return None
        except (TypeError, ValueError):
            return None
    return referral


def clear_session_referral(request):
    for key in (
        REFERRAL_SESSION_CODE_KEY,
        REFERRAL_SESSION_VISITOR_KEY,
        REFERRAL_SESSION_CAPTURED_AT_KEY,
    ):
        request.session.pop(key, None)


def _visitor_from_request(request):
    raw = request.session.get(REFERRAL_SESSION_VISITOR_KEY)
    try:
        return uuid.UUID(str(raw)) if raw else None
    except ValueError:
        return None


def _resolve_referral(*, order, referral_code=None, request=None):
    if isinstance(referral_code, str):
        return validate_referral_code(referral_code, event=order.event)
    if referral_code is not None:
        return validate_referral_code(referral_code.code, event=order.event)
    if request is not None:
        return get_session_referral(request, event=order.event)
    return None


@transaction.atomic
def attribute_order(*, order: TicketOrder, referral_code=None, request=None):
    existing = ReferralAttribution.objects.filter(order=order).first()
    if existing:
        return existing

    referral = _resolve_referral(order=order, referral_code=referral_code, request=request)
    if not referral:
        return None

    self_referral = bool(
        order.buyer_id
        and referral.partner.user_id
        and order.buyer_id == referral.partner.user_id
    )
    attribution = ReferralAttribution(
        order=order,
        referral_code=referral,
        campaign=referral.campaign,
        partner=referral.partner,
        visitor_id=_visitor_from_request(request) if request is not None else None,
        status=AttributionStatus.REVERSED if self_referral else AttributionStatus.PENDING,
        reversed_at=timezone.now() if self_referral else None,
    )
    attribution.save()
    if order.status == TicketOrderStatus.CONFIRMED and not self_referral:
        confirm_order_attribution(order=order)
    return attribution


def _commission_snapshot(referral: ReferralCode, order: TicketOrder):
    commission_type = referral.effective_commission_type
    commission_value = referral.effective_commission_value
    if commission_type == CommissionType.PERCENTAGE:
        amount = _quantize(order.total_amount * commission_value / Decimal("100"))
        currency = order.currency.upper()
    else:
        currency = referral.campaign.commission_currency.upper()
        if currency != order.currency.upper():
            return commission_type, commission_value, Decimal("0.00"), order.currency.upper()
        amount = _quantize(commission_value)
    return commission_type, commission_value, amount, currency


@transaction.atomic
def confirm_order_attribution(*, order: TicketOrder):
    try:
        attribution = (
            ReferralAttribution.objects.select_for_update()
            .select_related("referral_code", "referral_code__campaign", "partner", "order")
            .get(order=order)
        )
    except ReferralAttribution.DoesNotExist:
        return None

    if attribution.status == AttributionStatus.REVERSED:
        return attribution
    if attribution.status == AttributionStatus.CONFIRMED:
        return attribution

    locked_order = TicketOrder.objects.select_for_update().get(pk=order.pk)
    if locked_order.status != TicketOrderStatus.CONFIRMED:
        return attribution

    commission_type, commission_value, amount, currency = _commission_snapshot(
        attribution.referral_code,
        locked_order,
    )
    attribution.status = AttributionStatus.CONFIRMED
    attribution.confirmed_at = timezone.now()
    attribution.save(update_fields=["status", "confirmed_at"])

    # Free orders and fixed-currency mismatches remain valid conversions but do not
    # generate a zero/ambiguous financial liability.
    if amount <= 0:
        return attribution

    PartnerCommission.objects.get_or_create(
        attribution=attribution,
        defaults={
            "partner": attribution.partner,
            "campaign": attribution.campaign,
            "order": locked_order,
            "amount": amount,
            "currency": currency,
            "commission_type": commission_type,
            "commission_value": commission_value,
            "status": CommissionStatus.EARNED,
        },
    )
    return attribution


@transaction.atomic
def reverse_order_attribution(*, order: TicketOrder):
    try:
        attribution = ReferralAttribution.objects.select_for_update().get(order=order)
    except ReferralAttribution.DoesNotExist:
        return None
    if attribution.status == AttributionStatus.REVERSED:
        return attribution

    commission = PartnerCommission.objects.select_for_update().filter(attribution=attribution).first()
    if commission and commission.status == CommissionStatus.PAID:
        raise ValidationError(
            "Cette commande possède une commission déjà payée. Un ajustement financier manuel est requis avant annulation."
        )

    attribution.status = AttributionStatus.REVERSED
    attribution.reversed_at = timezone.now()
    attribution.save(update_fields=["status", "reversed_at"])
    if commission:
        commission.status = CommissionStatus.REVERSED
        commission.reversed_at = timezone.now()
        commission.save(update_fields=["status", "reversed_at", "updated_at"])
    return attribution


@transaction.atomic
def create_partner(*, organization, actor, name, email="", phone="", kind="ambassador", user=None, notes=""):
    if not user_can_manage_partners(actor, organization):
        raise PermissionDenied("Vous n’avez pas le droit de gérer les partenaires de cette organisation.")
    partner = Partner(
        organization=organization,
        user=user,
        name=name.strip(),
        email=(email or (getattr(user, "email", "") if user else "")).strip().lower(),
        phone=phone.strip(),
        kind=kind,
        notes=notes.strip(),
        created_by=actor,
        status=PartnerStatus.ACTIVE,
    )
    partner.full_clean()
    partner.save()
    return partner


@transaction.atomic
def create_campaign(
    *,
    organization,
    event,
    actor,
    name,
    commission_type,
    commission_value,
    commission_currency="USD",
    attribution_window_days=30,
    starts_at=None,
    ends_at=None,
    status=CampaignStatus.DRAFT,
):
    if not user_can_manage_partners(actor, organization):
        raise PermissionDenied("Vous n’avez pas le droit de gérer les campagnes de cette organisation.")
    campaign = AffiliateCampaign(
        organization=organization,
        event=event,
        name=name.strip(),
        commission_type=commission_type,
        commission_value=commission_value,
        commission_currency=commission_currency,
        attribution_window_days=attribution_window_days,
        starts_at=starts_at,
        ends_at=ends_at,
        status=status,
        created_by=actor,
    )
    campaign.full_clean()
    campaign.save()
    return campaign


@transaction.atomic
def create_referral_code(
    *,
    campaign,
    partner,
    actor,
    code="",
    commission_type_override="",
    commission_value_override=None,
):
    if not user_can_manage_partners(actor, campaign.organization):
        raise PermissionDenied("Vous n’avez pas le droit de créer des codes ambassadeurs.")
    referral = ReferralCode(
        campaign=campaign,
        partner=partner,
        code=(code or "").strip().upper(),
        commission_type_override=commission_type_override,
        commission_value_override=commission_value_override,
    )
    referral.full_clean()
    referral.save()
    return referral


def partner_balance(partner: Partner):
    rows = (
        PartnerCommission.objects.filter(
            partner=partner,
            status=CommissionStatus.EARNED,
            payout__isnull=True,
            amount__gt=0,
        )
        .values("currency")
        .annotate(total=Sum("amount"))
        .order_by("currency")
    )
    return [
        {"currency": row["currency"], "amount": row["total"] or Decimal("0")}
        for row in rows
        if (row["total"] or Decimal("0")) > 0
    ]


@transaction.atomic
def create_payout(*, partner: Partner, actor, currency: str, commission_ids=None, reference="", notes=""):
    organization = partner.organization
    if not user_can_manage_partner_payouts(actor, organization):
        raise PermissionDenied("Vous n’avez pas le droit de payer les commissions partenaires.")
    currency = currency.strip().upper()
    commissions = PartnerCommission.objects.select_for_update().filter(
        partner=partner,
        currency=currency,
        status=CommissionStatus.EARNED,
        payout__isnull=True,
        amount__gt=0,
    )
    if commission_ids:
        commissions = commissions.filter(pk__in=commission_ids)
    commissions = list(commissions)
    if not commissions:
        raise ValidationError("Aucune commission acquise n’est disponible dans cette devise.")
    amount = sum((commission.amount for commission in commissions), Decimal("0"))
    if amount <= 0:
        raise ValidationError("Le solde partenaire doit être strictement positif.")
    payout = PartnerPayout.objects.create(
        organization=organization,
        partner=partner,
        currency=currency,
        amount=amount,
        status=PayoutStatus.DRAFT,
        reference=reference.strip(),
        notes=notes.strip(),
        created_by=actor,
    )
    PartnerCommission.objects.filter(pk__in=[item.pk for item in commissions]).update(payout=payout)
    return payout


@transaction.atomic
def mark_payout_paid(*, payout: PartnerPayout, actor, reference=""):
    payout = PartnerPayout.objects.select_for_update().select_related("organization", "partner").get(pk=payout.pk)
    if not user_can_manage_partner_payouts(actor, payout.organization):
        raise PermissionDenied("Vous n’avez pas le droit de confirmer ce paiement de commissions.")
    if payout.status == PayoutStatus.PAID:
        return payout
    if payout.status == PayoutStatus.CANCELLED:
        raise ValidationError("Ce paiement de commissions est annulé.")
    commissions = list(payout.commissions.select_for_update().filter(status=CommissionStatus.EARNED))
    if not commissions:
        raise ValidationError("Ce paiement ne contient plus de commission payable.")
    now = timezone.now()
    payout.status = PayoutStatus.PAID
    payout.reference = (reference or payout.reference).strip()
    payout.paid_by = actor
    payout.paid_at = now
    payout.save(update_fields=["status", "reference", "paid_by", "paid_at", "updated_at"])
    PartnerCommission.objects.filter(pk__in=[item.pk for item in commissions]).update(
        status=CommissionStatus.PAID,
        paid_at=now,
        updated_at=now,
    )
    return payout


@transaction.atomic
def cancel_payout(*, payout: PartnerPayout, actor):
    payout = PartnerPayout.objects.select_for_update().select_related("organization").get(pk=payout.pk)
    if not user_can_manage_partner_payouts(actor, payout.organization):
        raise PermissionDenied("Vous n’avez pas le droit d’annuler ce paiement de commissions.")
    if payout.status == PayoutStatus.PAID:
        raise ValidationError("Un paiement déjà marqué comme payé ne peut pas être annulé ici.")
    if payout.status == PayoutStatus.CANCELLED:
        return payout
    payout.status = PayoutStatus.CANCELLED
    payout.save(update_fields=["status", "updated_at"])
    payout.commissions.filter(status=CommissionStatus.EARNED).update(
        payout=None,
        updated_at=timezone.now(),
    )
    return payout


def build_partner_metrics(partner: Partner, *, finance_visible=True):
    codes = ReferralCode.objects.filter(partner=partner)
    attributions = ReferralAttribution.objects.filter(partner=partner)
    commissions = PartnerCommission.objects.filter(partner=partner)
    visits = ReferralVisit.objects.filter(referral_code__partner=partner).count()
    confirmed = attributions.filter(status=AttributionStatus.CONFIRMED).count()
    orders = attributions.count()
    conversion = round((confirmed / visits) * 100, 1) if visits else None
    result = {
        "visits": visits,
        "attributed_orders": orders,
        "confirmed_orders": confirmed,
        "conversion_percent": conversion,
        "active_codes": codes.filter(is_active=True).count(),
    }
    if finance_visible:
        rows = commissions.values("currency", "status").annotate(total=Sum("amount"))
        money = {}
        for row in rows:
            currency = row["currency"]
            money.setdefault(
                currency,
                {
                    CommissionStatus.EARNED: Decimal("0"),
                    CommissionStatus.PAID: Decimal("0"),
                    CommissionStatus.REVERSED: Decimal("0"),
                },
            )
            money[currency][row["status"]] = row["total"] or Decimal("0")
        result["commissions"] = [
            {
                "currency": currency,
                "earned": values[CommissionStatus.EARNED],
                "paid": values[CommissionStatus.PAID],
                "reversed": values[CommissionStatus.REVERSED],
            }
            for currency, values in sorted(money.items())
        ]
    else:
        result["commissions"] = []
    return result
