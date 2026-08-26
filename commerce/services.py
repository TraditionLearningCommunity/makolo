from dataclasses import dataclass
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from capacity.models import CapacityReservationStatus
from capacity.services import commit_capacity, expire_capacity, release_capacity, reserve_capacity
from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event
from journeys.models import Journey, JourneyStatus, WorkflowKind
from journeys.services import confirm_journey, expire_journey, require_payment

from .models import (
    CommerceOrder,
    CommerceOrderItem,
    CommerceOrderStatus,
    Offer,
    OfferPaymentOption,
    OfferStatus,
    PaymentMode,
)


@dataclass(frozen=True)
class OrderSelection:
    offer: Offer
    quantity: int
    beneficiary: object | None = None
    external_beneficiary: object | None = None
    discount_total: Decimal = Decimal("0.00")


def _string_id(value):
    return str(value) if value else None


def _emit_order_event(order, *, event_type, activity_id, space_id, occurrence_id=None):
    suffix = event_type.rsplit(".", 1)[-1]
    return emit_domain_event(
        event_type=event_type,
        source_type="commerce_order",
        source_id=order.pk,
        idempotency_key=f"commerce-order:{order.pk}:{suffix}",
        space_id=space_id,
        activity_id=activity_id,
        payload={
            "commerce_order_id": str(order.pk),
            "journey_id": str(order.journey_id),
            "activity_id": str(activity_id),
            "occurrence_id": _string_id(occurrence_id),
            "buyer_id": _string_id(order.buyer_id),
            "payee_space_id": _string_id(order.payee_space_id),
            "payee_profile_id": _string_id(order.payee_profile_id),
            "payment_mode": order.payment_mode,
            "currency": order.currency,
            "amount": str(order.total),
            "status": order.status,
        },
    )


def _normalize_payment_modes(offer, modes):
    modes = list(dict.fromkeys(modes or [offer.payment_mode]))
    if not modes:
        modes = [offer.payment_mode]
    invalid = [mode for mode in modes if mode not in PaymentMode.values]
    if invalid:
        raise ValidationError("Mode de paiement Offer invalide.")
    if offer.payment_mode not in modes:
        raise ValidationError("Le mode de paiement par défaut doit faire partie des modes autorisés.")
    if offer.unit_price == Decimal("0.00"):
        if modes != [PaymentMode.NONE]:
            raise ValidationError("Une Offer gratuite accepte uniquement le mode sans paiement.")
    elif PaymentMode.NONE in modes:
        raise ValidationError("Une Offer payante ne peut pas proposer le mode sans paiement.")
    return modes


@transaction.atomic
def set_offer_payment_modes(*, offer, modes):
    offer = Offer.objects.select_for_update(of=("self",)).order_by().get(pk=offer.pk)
    modes = _normalize_payment_modes(offer, modes)
    OfferPaymentOption.objects.filter(offer=offer).exclude(mode__in=modes).delete()
    for mode in modes:
        OfferPaymentOption.objects.get_or_create(offer=offer, mode=mode)
    return offer


def create_offer(*, payment_modes=None, **values):
    offer = Offer(**values)
    offer.full_clean()
    offer.save()
    set_offer_payment_modes(offer=offer, modes=payment_modes or [offer.payment_mode])
    return offer


def update_offer(*, offer, payment_modes=None, **values):
    offer = Offer.objects.select_for_update(of=("self",)).order_by().get(pk=offer.pk)
    protected = {"id", "activity"}
    if protected & values.keys():
        raise ValidationError("L’Activity d’une Offer ne peut pas être déplacée par ce service.")
    for field, value in values.items():
        setattr(offer, field, value)
    offer.full_clean()
    offer.save()
    if payment_modes is not None:
        set_offer_payment_modes(offer=offer, modes=payment_modes)
    elif not offer.payment_options.exists():
        set_offer_payment_modes(offer=offer, modes=[offer.payment_mode])
    return offer


def _normalize_selection(raw):
    if isinstance(raw, OrderSelection):
        return raw
    if isinstance(raw, dict):
        return OrderSelection(
            offer=raw["offer"],
            quantity=raw.get("quantity", 1),
            beneficiary=raw.get("beneficiary"),
            external_beneficiary=raw.get("external_beneficiary"),
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


def _selection_holder(selection, journey):
    beneficiary = selection.beneficiary
    external = selection.external_beneficiary
    if beneficiary is None and external is None:
        beneficiary = journey.beneficiary
        external = journey.external_beneficiary
    if bool(beneficiary) == bool(external):
        raise ValidationError("Chaque ligne doit cibler exactement un bénéficiaire Profile ou externe.")
    if journey.beneficiary_id and getattr(beneficiary, "pk", None) != journey.beneficiary_id:
        raise ValidationError("Le bénéficiaire de la ligne doit correspondre à celui de la Démarche.")
    if journey.external_beneficiary_id and getattr(external, "pk", None) != journey.external_beneficiary_id:
        raise ValidationError("Le bénéficiaire externe de la ligne doit correspondre à celui de la Démarche.")
    return beneficiary, external


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
    payee_profile=None,
    payment_mode=None,
    expires_at=None,
    idempotency_key=None,
    source_key=None,
    promotion_code=None,
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

    journey = (
        Journey.objects.select_for_update(of=("self",))
        .select_related("beneficiary", "external_beneficiary", "activity", "activity__owner_profile")
        .order_by()
        .get(pk=journey.pk)
    )
    normalized = [_normalize_selection(raw) for raw in selections]
    if not normalized:
        raise ValidationError("Une commande doit contenir au moins une ligne.")

    offer_ids = [selection.offer.pk for selection in normalized]
    locked_offers = {
        offer.pk: offer
        for offer in Offer.objects.select_for_update(of=("self",))
        .filter(pk__in=offer_ids)
        .prefetch_related("payment_options")
        .order_by()
    }
    now = timezone.now()
    currencies = set()
    default_modes = set()
    subtotal = Decimal("0.00")
    discount_total = Decimal("0.00")
    prepared = []
    for selection in normalized:
        offer = locked_offers.get(selection.offer.pk)
        if offer is None:
            raise ValidationError("Offer introuvable.")
        quantity = _validate_offer_for_journey(offer, journey, selection.quantity, now=now)
        beneficiary, external_beneficiary = _selection_holder(selection, journey)
        line_subtotal = offer.unit_price * quantity
        line_discount = Decimal(selection.discount_total)
        if promotion_code and line_discount != Decimal("0.00"):
            raise ValidationError("Le montant de remise est calculé par le serveur lorsqu’un code Promotion est utilisé.")
        if line_discount < 0 or line_discount > line_subtotal:
            raise ValidationError("La remise de ligne est invalide.")
        currencies.add(offer.currency)
        default_modes.add(offer.payment_mode)
        subtotal += line_subtotal
        discount_total += line_discount
        prepared.append((offer, quantity, beneficiary, external_beneficiary, line_subtotal, line_discount))

    if len(currencies) != 1:
        raise ValidationError("Une commande ne peut pas mélanger plusieurs devises.")
    currency = currencies.pop()

    if payment_mode is None:
        chargeable_defaults = default_modes - {PaymentMode.NONE}
        if len(chargeable_defaults) > 1:
            raise ValidationError("Une commande ne peut pas mélanger plusieurs modes de paiement par défaut.")
        payment_mode = chargeable_defaults.pop() if chargeable_defaults else PaymentMode.NONE
    if payment_mode not in PaymentMode.values:
        raise ValidationError("Mode de paiement choisi invalide.")
    for offer, *_ in prepared:
        if not offer.allows_payment_mode(payment_mode):
            raise ValidationError(f"{offer.name} n’autorise pas ce mode de paiement.")

    activity_space_id, activity_owner_profile_id, activity_id, occurrence_id = Journey.objects.filter(pk=journey.pk).values_list(
        "activity__space_id", "activity__owner_profile_id", "activity_id", "occurrence_id"
    ).get()
    if payee_space is not None and payee_profile is not None:
        raise ValidationError("Une commande ne peut avoir qu’un seul bénéficiaire financier logique.")
    if payee_space is None and payee_profile is None:
        if activity_space_id is not None:
            from organizations.models import Organization
            payee_space = Organization.objects.get(pk=activity_space_id)
        elif activity_owner_profile_id is not None:
            from django.contrib.auth import get_user_model
            payee_profile = get_user_model().objects.get(pk=activity_owner_profile_id)
    if promotion_code and payee_space is None:
        raise ValidationError("Une Promotion nécessite un Espace bénéficiaire explicite.")

    promotion_quote = None
    if promotion_code:
        from promotions.canonical_services import allocate_discount, quote_commerce_promotion

        promotion_profile = buyer if getattr(buyer, "is_authenticated", False) else journey.beneficiary
        promotion_quote = quote_commerce_promotion(
            code_value=promotion_code,
            buyer=promotion_profile,
            customer_email=getattr(promotion_profile, "email", "") or "",
            selections=[(row[0], row[1]) for row in prepared],
            subtotal_amount=subtotal,
            currency=currency,
            payee_space=payee_space,
            now=now,
        )
        prepared = allocate_discount(prepared=prepared, quote=promotion_quote)
        discount_total = promotion_quote["discount_amount"]

    total = subtotal - discount_total
    if payment_mode == PaymentMode.NONE and total != Decimal("0.00"):
        raise ValidationError("Une commande payment_mode=none doit être gratuite.")
    if total == Decimal("0.00") and payment_mode != PaymentMode.NONE:
        raise ValidationError("Une commande gratuite doit utiliser le mode sans paiement.")

    order = CommerceOrder(
        journey=journey,
        buyer=buyer if getattr(buyer, "is_authenticated", False) else None,
        payee_space=payee_space,
        payee_profile=payee_profile,
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

    for index, (offer, quantity, beneficiary, external_beneficiary, line_subtotal, line_discount) in enumerate(prepared):
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
            external_beneficiary=external_beneficiary,
            capacity_reservation=reservation,
            quantity=quantity,
            label_snapshot=offer.name,
            unit_price=offer.unit_price,
            line_subtotal=line_subtotal,
            discount_total=line_discount,
            line_total=line_subtotal - line_discount,
        )

    if promotion_quote:
        from promotions.canonical_services import create_commerce_redemption
        create_commerce_redemption(order=order, quote=promotion_quote)

    _emit_order_event(
        order,
        event_type=DomainEventType.COMMERCE_ORDER_CREATED,
        activity_id=activity_id,
        space_id=activity_space_id,
        occurrence_id=occurrence_id,
    )
    _prepare_journey_payment_state(journey, payment_mode)
    return order


def _successful_payment_exists(order):
    from payments.models import Payment, PaymentStatus
    return Payment.objects.filter(commerce_order=order, status=PaymentStatus.SUCCEEDED).exists()


def _order_scope(order):
    return Journey.objects.filter(pk=order.journey_id).values_list(
        "activity__space_id", "activity_id", "occurrence_id"
    ).get()


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
    order = _set_order_status(order, CommerceOrderStatus.CONFIRMED)
    try:
        from promotions.canonical_services import confirm_commerce_redemption
        confirm_commerce_redemption(order=order)
    except ImportError:
        pass
    space_id, activity_id, occurrence_id = _order_scope(order)
    _emit_order_event(
        order,
        event_type=DomainEventType.COMMERCE_ORDER_CONFIRMED,
        activity_id=activity_id,
        space_id=space_id,
        occurrence_id=occurrence_id,
    )
    return order


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
    order = _set_order_status(order, CommerceOrderStatus.CANCELLED)
    try:
        from promotions.canonical_services import reverse_commerce_redemption
        reverse_commerce_redemption(order=order)
    except ImportError:
        pass
    space_id, activity_id, occurrence_id = _order_scope(order)
    _emit_order_event(
        order,
        event_type=DomainEventType.COMMERCE_ORDER_CANCELLED,
        activity_id=activity_id,
        space_id=space_id,
        occurrence_id=occurrence_id,
    )
    return order


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
    order = _set_order_status(order, CommerceOrderStatus.EXPIRED, now=now)
    try:
        from promotions.canonical_services import reverse_commerce_redemption
        reverse_commerce_redemption(order=order)
    except ImportError:
        pass
    space_id, activity_id, occurrence_id = _order_scope(order)
    _emit_order_event(
        order,
        event_type=DomainEventType.COMMERCE_ORDER_EXPIRED,
        activity_id=activity_id,
        space_id=space_id,
        occurrence_id=occurrence_id,
    )
    return order
