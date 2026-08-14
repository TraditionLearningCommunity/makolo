from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from capacity.models import CapacityPool, CapacityReservation, CapacityReservationStatus
from capacity.selectors import capacity_availability
from capacity.services import commit_capacity, expire_capacity, release_capacity, reserve_capacity
from commerce.models import CommerceOrder, CommerceOrderItem, CommerceOrderStatus, Offer, OfferStatus, PaymentMode
from events.activity_bridge import sync_event_core

from .journey_access_bridge import sync_order_journey
from .models import TicketOrder, TicketOrderItem, TicketOrderStatus, TicketType


ORDER_STATUS_MAP = {
    TicketOrderStatus.PENDING: CommerceOrderStatus.PENDING,
    TicketOrderStatus.CONFIRMED: CommerceOrderStatus.CONFIRMED,
    TicketOrderStatus.CANCELLED: CommerceOrderStatus.CANCELLED,
    TicketOrderStatus.EXPIRED: CommerceOrderStatus.EXPIRED,
}

RESERVATION_STATUS_MAP = {
    TicketOrderStatus.PENDING: CapacityReservationStatus.HELD,
    TicketOrderStatus.CONFIRMED: CapacityReservationStatus.COMMITTED,
    TicketOrderStatus.CANCELLED: CapacityReservationStatus.RELEASED,
    TicketOrderStatus.EXPIRED: CapacityReservationStatus.EXPIRED,
}


def _offer_payment_mode(ticket_type):
    return PaymentMode.NONE if ticket_type.price == 0 else PaymentMode.UPFRONT


def _offer_status(ticket_type):
    return OfferStatus.ACTIVE if ticket_type.is_active else OfferStatus.INACTIVE


@transaction.atomic
def sync_ticket_type_commerce(ticket_type: TicketType):
    ticket_type = (
        TicketType.objects.select_for_update(of=("self",))
        .select_related("event__activity", "offer", "capacity_pool")
        .order_by()
        .get(pk=ticket_type.pk)
    )
    activity, occurrence = sync_event_core(ticket_type.event)

    pool = ticket_type.capacity_pool
    if pool is None:
        pool, _ = CapacityPool.objects.get_or_create(
            source_key=f"ticket-type:{ticket_type.pk}",
            defaults={
                "activity": activity,
                "occurrence": occurrence,
                "label": ticket_type.name,
                "total_quantity": ticket_type.quantity_total,
                "is_active": ticket_type.is_active,
            },
        )
    else:
        if pool.activity_id != activity.pk or pool.occurrence_id != occurrence.pk:
            raise ValidationError("Le CapacityPool du type de billet est incohérent avec son Event.")
        availability = capacity_availability(pool)
        consumed = availability.held + availability.committed
        if ticket_type.quantity_total is not None and consumed > ticket_type.quantity_total:
            raise ValidationError("Le nouveau stock est inférieur à la capacité déjà retenue ou engagée.")
        CapacityPool.objects.filter(pk=pool.pk).update(
            label=ticket_type.name,
            total_quantity=ticket_type.quantity_total,
            is_active=ticket_type.is_active,
        )
        pool.refresh_from_db()

    offer = ticket_type.offer
    offer_values = {
        "activity": activity,
        "occurrence": occurrence,
        "capacity_pool": pool,
        "name": ticket_type.name,
        "description": ticket_type.description,
        "unit_price": ticket_type.price,
        "currency": ticket_type.currency,
        "payment_mode": _offer_payment_mode(ticket_type),
        "available_from": ticket_type.sales_start_at,
        "available_until": ticket_type.sales_end_at,
        "min_quantity": ticket_type.min_per_order,
        "max_quantity": ticket_type.max_per_order,
        "status": _offer_status(ticket_type),
    }
    if offer is None:
        offer, _ = Offer.objects.get_or_create(
            source_key=f"ticket-type:{ticket_type.pk}",
            defaults=offer_values,
        )
    else:
        for field, value in offer_values.items():
            setattr(offer, field, value)
        offer.save()

    TicketType.objects.filter(pk=ticket_type.pk).update(offer=offer, capacity_pool=pool)
    ticket_type.offer = offer
    ticket_type.capacity_pool = pool
    return offer, pool


def _sync_commerce_order_status(commerce_order, target_status):
    if commerce_order.status == target_status:
        return commerce_order
    CommerceOrder.objects.filter(pk=commerce_order.pk).update(status=target_status)
    commerce_order.status = target_status
    return commerce_order


def _sync_item_reservation_status(reservation, order):
    target = RESERVATION_STATUS_MAP[order.status]
    if reservation.status == target:
        if target == CapacityReservationStatus.HELD and reservation.expires_at != order.expires_at:
            CapacityReservation.objects.filter(pk=reservation.pk).update(expires_at=order.expires_at)
            reservation.expires_at = order.expires_at
        return reservation
    if target == CapacityReservationStatus.COMMITTED:
        return commit_capacity(reservation=reservation)
    if target == CapacityReservationStatus.RELEASED:
        return release_capacity(reservation=reservation, allow_committed=True)
    if target == CapacityReservationStatus.EXPIRED:
        if reservation.status == CapacityReservationStatus.HELD:
            if reservation.expires_at is None:
                CapacityReservation.objects.filter(pk=reservation.pk).update(expires_at=order.expires_at)
                reservation.expires_at = order.expires_at
            return expire_capacity(reservation=reservation, now=order.expires_at)
        return reservation
    return reservation


def _sync_order_totals(ticket_order, commerce_order):
    legacy_items = list(ticket_order.items.select_related("commerce_item").order_by("created_at", "id"))
    subtotal = sum((item.unit_price * item.quantity for item in legacy_items), Decimal("0.00"))
    if subtotal < ticket_order.total_amount:
        subtotal = ticket_order.total_amount
    discount = subtotal - ticket_order.total_amount
    remaining_discount = discount
    for item in legacy_items:
        commerce_item = item.commerce_item
        if commerce_item is None:
            continue
        line_subtotal = item.unit_price * item.quantity
        line_discount = min(line_subtotal, remaining_discount)
        remaining_discount -= line_discount
        CommerceOrderItem.objects.filter(pk=commerce_item.pk).update(
            quantity=item.quantity,
            label_snapshot=item.ticket_type.name,
            unit_price=item.unit_price,
            line_subtotal=line_subtotal,
            discount_total=line_discount,
            line_total=line_subtotal - line_discount,
        )
    CommerceOrder.objects.filter(pk=commerce_order.pk).update(
        currency=ticket_order.currency,
        payment_mode=PaymentMode.NONE if ticket_order.total_amount == 0 else PaymentMode.UPFRONT,
        subtotal=subtotal,
        discount_total=discount,
        total=ticket_order.total_amount,
        expires_at=ticket_order.expires_at,
        confirmed_at=ticket_order.confirmed_at,
        cancelled_at=ticket_order.cancelled_at,
    )
    commerce_order.refresh_from_db()
    return commerce_order


@transaction.atomic
def sync_order_commerce(order: TicketOrder):
    order = (
        TicketOrder.objects.select_for_update(of=("self",))
        .select_related("event__activity", "journey", "commerce_order", "buyer")
        .order_by()
        .get(pk=order.pk)
    )
    journey = order.journey or sync_order_journey(order)
    if journey is None:
        # Historical guest compatibility: Task 6 intentionally does not invent a
        # Profile/Journey when the holder cannot be identified deterministically.
        return None
    activity, _ = sync_event_core(order.event)
    payee_space = activity.space
    target_status = ORDER_STATUS_MAP[order.status]
    commerce_order = order.commerce_order
    if commerce_order is None:
        commerce_order, _ = CommerceOrder.objects.get_or_create(
            source_key=f"ticket-order:{order.pk}",
            defaults={
                "journey": journey,
                "buyer": order.buyer,
                "payee_space": payee_space,
                "status": target_status,
                "currency": order.currency,
                "payment_mode": PaymentMode.NONE if order.total_amount == 0 else PaymentMode.UPFRONT,
                "subtotal": order.total_amount,
                "discount_total": Decimal("0.00"),
                "total": order.total_amount,
                "expires_at": order.expires_at,
                "confirmed_at": order.confirmed_at,
                "cancelled_at": order.cancelled_at,
            },
        )
        TicketOrder.objects.filter(pk=order.pk).update(commerce_order=commerce_order)
        order.commerce_order = commerce_order
    else:
        if commerce_order.journey_id != journey.pk:
            raise ValidationError("Le bridge TicketOrder pointe vers une CommerceOrder d’une autre Démarche.")
        if payee_space is not None and commerce_order.payee_space_id not in {None, payee_space.pk}:
            raise ValidationError("Le bénéficiaire financier du bridge TicketOrder est incohérent.")
        CommerceOrder.objects.filter(pk=commerce_order.pk).update(
            buyer_id=order.buyer_id,
            payee_space_id=getattr(payee_space, "pk", None),
        )
        commerce_order.refresh_from_db()
    _sync_commerce_order_status(commerce_order, target_status)
    return _sync_order_totals(order, commerce_order)


@transaction.atomic
def sync_order_item_commerce(item: TicketOrderItem):
    item = (
        TicketOrderItem.objects.select_for_update(of=("self",))
        .select_related(
            "order__journey",
            "order__commerce_order",
            "ticket_type__offer",
            "ticket_type__capacity_pool",
            "commerce_item__capacity_reservation",
        )
        .order_by()
        .get(pk=item.pk)
    )
    offer, pool = sync_ticket_type_commerce(item.ticket_type)
    commerce_order = item.order.commerce_order or sync_order_commerce(item.order)
    if commerce_order is None:
        return None

    commerce_item = item.commerce_item
    reservation = commerce_item.capacity_reservation if commerce_item else None
    if reservation is None:
        source_key = f"ticket-item:{item.pk}"
        existing = CapacityReservation.objects.filter(pool=pool, journey=commerce_order.journey, source_key=source_key).first()
        if existing:
            reservation = existing
        elif item.order.status == TicketOrderStatus.PENDING and item.order.is_expired:
            # Compatibility for historical/demo legacy rows whose temporary TicketOrder
            # hold had already elapsed before the canonical Capacity bridge existed.
            # They must not consume capacity, and runtime reserve_capacity remains strict.
            reservation = CapacityReservation.objects.create(
                pool=pool,
                journey=commerce_order.journey,
                quantity=item.quantity,
                status=CapacityReservationStatus.EXPIRED,
                expires_at=item.order.expires_at,
                source_key=source_key,
            )
        else:
            reservation = reserve_capacity(
                pool=pool,
                journey=commerce_order.journey,
                quantity=item.quantity,
                expires_at=item.order.expires_at if item.order.status == TicketOrderStatus.PENDING else None,
                source_key=source_key,
            )

    # Existing reservations must follow the TicketOrder lifecycle as well. Without
    # this, an Event order could remain HELD forever after confirmation/cancellation
    # and keep the waitlist sold out even though the legacy Event projection released it.
    reservation = _sync_item_reservation_status(reservation, item.order)

    line_subtotal = item.unit_price * item.quantity
    if commerce_item is None:
        commerce_item = CommerceOrderItem.objects.create(
            order=commerce_order,
            offer=offer,
            beneficiary=item.order.buyer,
            capacity_reservation=reservation,
            quantity=item.quantity,
            label_snapshot=item.ticket_type.name,
            unit_price=item.unit_price,
            line_subtotal=line_subtotal,
            discount_total=Decimal("0.00"),
            line_total=line_subtotal,
        )
        TicketOrderItem.objects.filter(pk=item.pk).update(commerce_item=commerce_item)
        item.commerce_item = commerce_item
    else:
        if commerce_item.order_id != commerce_order.pk or commerce_item.offer_id != offer.pk:
            raise ValidationError("La ligne Event pointe vers une ligne Commerce incohérente.")
        CommerceOrderItem.objects.filter(pk=commerce_item.pk).update(
            capacity_reservation_id=reservation.pk,
            quantity=item.quantity,
            label_snapshot=item.ticket_type.name,
            unit_price=item.unit_price,
            line_subtotal=line_subtotal,
            line_total=line_subtotal - commerce_item.discount_total,
        )
    _sync_order_totals(item.order, commerce_order)
    return commerce_item


def sync_order_items(order):
    for item in order.items.all().order_by("created_at", "id"):
        sync_order_item_commerce(item)


def committed_reservation_for_ticket(ticket):
    item = (
        TicketOrderItem.objects.select_related("commerce_item__capacity_reservation")
        .filter(order=ticket.order, ticket_type=ticket.ticket_type)
        .first()
    )
    if not item or not item.commerce_item_id or not item.commerce_item.capacity_reservation_id:
        return None
    reservation = item.commerce_item.capacity_reservation
    if reservation.status != CapacityReservationStatus.COMMITTED:
        raise ValidationError("La capacité du billet n’est pas engagée.")
    return reservation


@receiver(post_save, sender=TicketType, dispatch_uid="tickets.sync_ticket_type_commerce")
def _ticket_type_saved(sender, instance, **kwargs):
    offer, pool = sync_ticket_type_commerce(instance)
    instance.offer = offer
    instance.capacity_pool = pool


@receiver(post_save, sender=TicketOrder, dispatch_uid="tickets.sync_order_commerce")
def _ticket_order_saved(sender, instance, **kwargs):
    commerce_order = sync_order_commerce(instance)
    if commerce_order is not None:
        instance.commerce_order = commerce_order
        # Order status changes (confirm/cancel/expire) must transition the canonical
        # reservation before any on_commit waitlist promotion sees availability.
        sync_order_items(instance)


@receiver(post_save, sender=TicketOrderItem, dispatch_uid="tickets.sync_order_item_commerce")
def _ticket_order_item_saved(sender, instance, **kwargs):
    commerce_item = sync_order_item_commerce(instance)
    if commerce_item is not None:
        instance.commerce_item = commerce_item