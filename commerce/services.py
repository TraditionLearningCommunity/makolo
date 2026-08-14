from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from capacity.models import CapacityReservationStatus
from capacity.services import commit_capacity, expire_capacity, release_capacity, reserve_capacity
from journeys.models import Journey, JourneyStatus, WorkflowKind
from journeys.services import confirm_journey, expire_journey, require_payment

from .models import CommerceOrder, CommerceOrderItem, CommerceOrderStatus, Offer, OfferStatus, PaymentMode


@dataclass(frozen=True)
class OrderSelection:
    offer: Offer
    quantity: int
    beneficiary: object | None = None
    discount_total: Decimal = Decimal("0.00")


def create_offer(**values):
    offer = Offer(**values)
    offer.full_clean()
    offer.save()
    return offer


def update_offer(*, offer, **values):
    offer = Offer.objects.select_for_update(of=("self",)).order_by().get(pk=offer.pk)
    protected = {"id", "activity"}
    if protected & values.keys():
        raise ValidationError("L’Activity d’une Offer ne peut pas être déplacée par ce service.")
    for field, value in values.items():
        setattr(offer, field, value)
    offer.full_clean()
    offer.save()
    return offer


def _normalize_selection(raw):
    if isinstance(raw, OrderSelection):
        return raw
    if isinstance(raw, dict):
        return OrderSelection(
            offer=raw["offer"],
            quantity=raw.get("quantity", 1),
            beneficiary=raw.get("beneficiary"),
            discount_total=Decimal(str(raw.get("discount_total", "0.00"))),
        )
    if isinstance(raw, (tuple, list)):
        if len(raw) == 2:
            return OrderSelection(raw[0], raw[1])
        if len(raw) == 3:
            return OrderSelection(raw[0], raw[1], raw[2])
    raise ValidationError("Sélection Commerce invalide.")


def _validate_offer_for_journey(offer, journey, quantity, *, now):
    if offer.activity_id != journey.activity_id:
        raise ValidationError("Une Offer appartient à une autre Activity que la Démarche.")
    if offer.occurrence_id and journey.occurrence_id != offer.occurrence_id:
        raise ValidationError("La Démarche ne cible pas l’Occurrence de cette Offer.")
    if offer.status != OfferStatus.ACTIVE:
        raise ValidationError(f"{offer.name} n’est pas active.")
    if offer.available_from and now < offer.available_from:
        raise ValidationError(f"{offer.name} n’est pas encore disponible.")
    if offer.available_until and now >= offer.available_until:
        raise ValidationError(f"{offer.name} n’est plus disponible.")
    try:
        quantity = int(quantity)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Quantité invalide.") from exc
    if quantity < offer.min_quantity:
        raise ValidationError(f"{offer.name}: quantité minimale {offer.min_quantity}.")
    if offer.max_quantity is not None and quantity > offer.max_quantity:
        raise ValidationError(f"{offer.name}: quantité maximale {offer.max_quantity}.")
    return quantity


def _set_order_status(order, status, *, now=None):
    now = now or timezone.now()
    order.status = status
    if status == CommerceOrderStatus.CONFIRMED and order.confirmed_at is None:
        order.confirmed_at = now
        order.expires_at = None
    elif status == CommerceOrderStatus.CANCELLED and order.cancelled_at is None:
        order.cancelled_at = now
        order.expires_at = None
    order._allow_status_transition = True
    order.save()
    return order


def _prepare_journey_payment_state(journey, payment_mode):
    if payment_mode == PaymentMode.UPFRONT:
        if journey.status == JourneyStatus.PENDING_PAYMENT:
            return journey
        if journey.workflow == WorkflowKind.PURCHASE and journey.status == JourneyStatus.DRAFT:
            return require_payment(journey=journey, reason="commerce_upfront")
        raise ValidationError("Le paiement upfront n’est pas cohérent avec l’état de la Démarche.")
    if payment_mode == PaymentMode.AFTER_APPROVAL:
        if journey.status == JourneyStatus.PENDING_PAYMENT:
            return journey
        if journey.status != JourneyStatus.APPROVED:
            raise ValidationError("Le paiement after_approval exige une Démarche approuvée.")
        return require_payment(journey=journey, reason="commerce_after_approval")
    return journey


@transaction.atomic
def create_order(
    *,
    journey,
    buyer,
    selections,
    payee_space=None,
    expires_at=None,
    idempotency_key=None,
    source_key=None,
):
    if idempotency_key:
        existing = CommerceOrder.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            if existing.journey_id != journey.pk:
                raise ValidationError("Cette clé d’idempotence appartient à une autre Démarche.")
            return existing
    if source_key:
        existing = CommerceOrder.objects.filter(source_key=source_key).first()
        if existing:
            if existing.journey_id != journey.pk:
                raise ValidationError("Cette référence source appartient à une autre Démarche.")
            return existing

    journey = Journey.objects.select_for_update(of=("self",)).order_by().get(pk=journey.pk)
    normalized = [_normalize_selection(raw) for raw in selections]
    if not normalized:
        raise ValidationError("Une commande doit contenir au moins une ligne.")

    offer_ids = [selection.offer.pk for selection in normalized]
    locked_offers = {
        offer.pk: offer
        for offer in Offer.objects.select_for_update(of=("self",)).filter(pk__in=offer_ids).order_by()
    }
    now = timezone.now()
    currencies = set()
    payment_modes = set()
    subtotal = Decimal("0.00")
    discount_total = Decimal("0.00")
    prepared = []
    for selection in normalized:
        offer = locked_offers.get(selection.offer.pk)
        if offer is None:
            raise ValidationError("Offer introuvable.")
        quantity = _validate_offer_for_journey(offer, journey, selection.quantity, now=now)
        line_subtotal = offer.unit_price * quantity
        line_discount = Decimal(selection.discount_total)
        if line_discount < 0 or line_discount > line_subtotal:
            raise ValidationError("La remise de ligne est invalide.")
        currencies.add(offer.currency)
        payment_modes.add(offer.payment_mode)
        subtotal += line_subtotal
        discount_total += line_discount
        prepared.append((offer, quantity, selection.beneficiary, line_subtotal, line_discount))

    if len(currencies) != 1:
        raise ValidationError("Une commande ne peut pas mélanger plusieurs devises.")
    if len(payment_modes) != 1:
        raise ValidationError("Une commande ne peut pas mélanger plusieurs modes de paiement.")
    currency = currencies.pop()
    payment_mode = payment_modes.pop()
    total = subtotal - discount_total
    if payment_mode == PaymentMode.NONE and total != Decimal("0.00"):
        raise ValidationError("Une commande payment_mode=none doit être gratuite.")

    activity_space_id = Journey.objects.filter(pk=journey.pk).values_list("activity__space_id", flat=True).get()
    if payee_space is None:
        if activity_space_id is None:
            raise ValidationError("Un bénéficiaire financier explicite est requis pour cette Activity.")
        from organizations.models import Organization
        payee_space = Organization.objects.get(pk=activity_space_id)
    if activity_space_id is not None and payee_space.pk != activity_space_id:
        raise ValidationError("Cette première version ne permet pas de mélanger plusieurs bénéficiaires financiers.")

    order = CommerceOrder(
        journey=journey,
        buyer=buyer if getattr(buyer, "is_authenticated", False) else None,
        payee_space=payee_space,
        status=CommerceOrderStatus.PENDING,
        currency=currency,
        payment_mode=payment_mode,
        subtotal=subtotal,
        discount_total=discount_total,
        total=total,
        expires_at=expires_at,
        idempotency_key=idempotency_key or None,
        source_key=source_key or None,
    )
    order.full_clean()
    try:
        order.save()
    except IntegrityError as exc:
        if idempotency_key:
            existing = CommerceOrder.objects.filter(idempotency_key=idempotency_key).first()
            if existing:
                return existing
        if source_key:
            existing = CommerceOrder.objects.filter(source_key=source_key).first()
            if existing:
                return existing
        raise ValidationError("Impossible de créer cette commande de façon unique.") from exc

    for index, (offer, quantity, beneficiary, line_subtotal, line_discount) in enumerate(prepared):
        reservation = None
        if offer.capacity_pool_id:
            reservation = reserve_capacity(
                pool=offer.capacity_pool,
                journey=journey,
                quantity=quantity,
                expires_at=expires_at,
                source_key=f"commerce:{order.pk}:{index}",
            )
        CommerceOrderItem.objects.create(
            order=order,
            offer=offer,
            beneficiary=beneficiary,
            capacity_reservation=reservation,
            quantity=quantity,
            label_snapshot=offer.name,
            unit_price=offer.unit_price,
            line_subtotal=line_subtotal,
            discount_total=line_discount,
            line_total=line_subtotal - line_discount,
        )

    _prepare_journey_payment_state(journey, payment_mode)
    return order


def _successful_payment_exists(order):
    from payments.models import Payment, PaymentStatus
    return Payment.objects.filter(commerce_order=order, status=PaymentStatus.SUCCEEDED).exists()


@transaction.atomic
def confirm_order(*, order, actor=None, payment_verified=False):
    order = CommerceOrder.objects.select_for_update(of=("self",)).order_by().get(pk=order.pk)
    if order.status == CommerceOrderStatus.CONFIRMED:
        return order
    if order.status not in {CommerceOrderStatus.PENDING, CommerceOrderStatus.DRAFT}:
        raise ValidationError("Cette commande ne peut pas être confirmée depuis son état actuel.")
    if order.expires_at and order.expires_at <= timezone.now():
        raise ValidationError("Cette commande a expiré.")
    if order.payment_mode in {PaymentMode.UPFRONT, PaymentMode.AFTER_APPROVAL} and order.total > 0:
        if not payment_verified and not _successful_payment_exists(order):
            raise ValidationError("Un paiement réussi est requis avant confirmation de cette commande.")

    items = list(order.items.select_related("capacity_reservation").order_by("created_at", "id"))
    for item in items:
        if item.capacity_reservation_id:
            commit_capacity(reservation=item.capacity_reservation)

    journey = Journey.objects.get(pk=order.journey_id)
    if journey.status != JourneyStatus.CONFIRMED:
        confirm_journey(journey=journey, actor=actor, reason="commerce_order_confirmed")
    return _set_order_status(order, CommerceOrderStatus.CONFIRMED)


@transaction.atomic
def cancel_order(*, order, actor=None, release_committed=False):
    order = CommerceOrder.objects.select_for_update(of=("self",)).order_by().get(pk=order.pk)
    if order.status == CommerceOrderStatus.CANCELLED:
        return order
    if order.status in {CommerceOrderStatus.EXPIRED, CommerceOrderStatus.REFUNDED}:
        return order
    for item in order.items.select_related("capacity_reservation").all():
        reservation = item.capacity_reservation
        if not reservation:
            continue
        if reservation.status == CapacityReservationStatus.HELD:
            release_capacity(reservation=reservation)
        elif reservation.status == CapacityReservationStatus.COMMITTED and release_committed:
            release_capacity(reservation=reservation, allow_committed=True)
    return _set_order_status(order, CommerceOrderStatus.CANCELLED)


@transaction.atomic
def expire_order(*, order, now=None):
    now = now or timezone.now()
    order = CommerceOrder.objects.select_for_update(of=("self",)).order_by().get(pk=order.pk)
    if order.status == CommerceOrderStatus.EXPIRED:
        return order
    if order.status != CommerceOrderStatus.PENDING or order.expires_at is None or order.expires_at > now:
        return order
    for item in order.items.select_related("capacity_reservation").all():
        reservation = item.capacity_reservation
        if not reservation or reservation.status != CapacityReservationStatus.HELD:
            continue
        if reservation.expires_at and reservation.expires_at <= now:
            expire_capacity(reservation=reservation, now=now)
        else:
            release_capacity(reservation=reservation, now=now)
    Journey.objects.filter(pk=order.journey_id).update(expires_at=now)
    journey = Journey.objects.get(pk=order.journey_id)
    expire_journey(journey=journey, now=now, reason="commerce_order_expired")
    return _set_order_status(order, CommerceOrderStatus.EXPIRED, now=now)
