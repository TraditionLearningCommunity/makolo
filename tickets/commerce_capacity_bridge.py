from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from capacity.models import CapacityReservationStatus
from capacity.services import commit_capacity, expire_capacity, release_capacity, reserve_capacity
from commerce.models import CommerceOrder, CommerceOrderItem, CommerceOrderStatus, PaymentMode

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


@transaction.atomic
def sync_ticket_type_commerce(ticket_type: TicketType):
    """Legacy bridge name retained; Task 9 never writes Offer/Capacity from TicketType.

    A Task 9 TicketType is only valid when both canonical objects already exist.
    """
    ticket_type = (
        TicketType.objects.select_for_update(of=("self",))
        .select_related("event__activity", "offer", "capacity_pool")
        .order_by()
        .get(pk=ticket_type.pk)
    )
    if not ticket_type.offer_id or not ticket_type.capacity_pool_id:
        raise ValidationError("Ce type de billet legacy n’a pas été converti vers Offer/CapacityPool.")
    if ticket_type.offer.activity_id != ticket_type.event.activity_id:
        raise ValidationError("L’Offer du type de billet appartient à une autre Activity.")
    if ticket_type.capacity_pool.activity_id != ticket_type.event.activity_id:
        raise ValidationError("Le CapacityPool du type de billet appartient à une autre Activity.")
    if ticket_type.offer.capacity_pool_id != ticket_type.capacity_pool_id:
        raise ValidationError("L’Offer du type de billet n’utilise pas son CapacityPool canonique.")
    return ticket_type.offer, ticket_type.capacity_pool


def _transition_legacy_reservation(reservation, order):
    target = RESERVATION_STATUS_MAP[order.status]
    if reservation.status == target:
        return reservation
    if target == CapacityReservationStatus.COMMITTED:
        return commit_capacity(reservation=reservation)
    if target == CapacityReservationStatus.RELEASED:
        return release_capacity(reservation=reservation, allow_committed=True)
    if target == CapacityReservationStatus.EXPIRED:
        if reservation.status == CapacityReservationStatus.HELD:
            if reservation.expires_at is None:
                reservation.expires_at = order.expires_at
                reservation.save(update_fields=["expires_at", "updated_at"])
            return expire_capacity(reservation=reservation, now=order.expires_at)
    return reservation


@transaction.atomic
def sync_order_commerce(order: TicketOrder):
    """Backfill-only compatibility for a legacy TicketOrder missing CommerceOrder.

    New Event checkout creates CommerceOrder first and links the TicketOrder
    projection afterwards, so an existing canonical order is never overwritten.
    """
    order = (
        TicketOrder.objects.select_for_update(of=("self",))
        .select_related("event__activity", "journey", "commerce_order", "buyer")
        .order_by()
        .get(pk=order.pk)
    )
    if order.commerce_order_id:
        return order.commerce_order

    journey = order.journey or sync_order_journey(order)
    if journey is None:
        # Historical guest compatibility: never invent a Profile.
        return None

    subtotal = sum(
        (item.unit_price * item.quantity for item in order.items.all()),
        Decimal("0.00"),
    )
    if subtotal < order.total_amount:
        subtotal = order.total_amount
    discount_total = subtotal - order.total_amount
    commerce_order, _ = CommerceOrder.objects.get_or_create(
        source_key=f"ticket-order:{order.pk}",
        defaults={
            "journey": journey,
            "buyer": order.buyer,
            "payee_space": order.event.activity.space,
            "status": ORDER_STATUS_MAP[order.status],
            "currency": order.currency,
            "payment_mode": PaymentMode.NONE if order.total_amount == 0 else PaymentMode.UPFRONT,
            "subtotal": subtotal,
            "discount_total": discount_total,
            "total": order.total_amount,
            "expires_at": order.expires_at,
            "confirmed_at": order.confirmed_at,
            "cancelled_at": order.cancelled_at,
        },
    )
    TicketOrder.objects.filter(pk=order.pk).update(commerce_order=commerce_order)
    order.commerce_order = commerce_order
    return commerce_order


@transaction.atomic
def sync_order_item_commerce(item: TicketOrderItem):
    """Backfill-only compatibility for an Event line missing CommerceOrderItem."""
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
    if item.commerce_item_id:
        return item.commerce_item

    offer, pool = sync_ticket_type_commerce(item.ticket_type)
    commerce_order = item.order.commerce_order or sync_order_commerce(item.order)
    if commerce_order is None:
        return None

    source_key = f"ticket-item:{item.pk}"
    reservation = pool.reservations.filter(
        journey=commerce_order.journey,
        source_key=source_key,
    ).first()
    if reservation is None:
        if item.order.status == TicketOrderStatus.PENDING and item.order.is_expired:
            from capacity.models import CapacityReservation

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
            reservation = _transition_legacy_reservation(reservation, item.order)

    line_subtotal = item.unit_price * item.quantity
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
    return commerce_item


def sync_order_items(order):
    for item in order.items.all().order_by("created_at", "id"):
        if not item.commerce_item_id:
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
    # Validation only: canonical objects were created by configure_ticket_type.
    sync_ticket_type_commerce(instance)


@receiver(post_save, sender=TicketOrder, dispatch_uid="tickets.sync_order_commerce")
def _ticket_order_saved(sender, instance, **kwargs):
    # Never project legacy state over an existing canonical CommerceOrder.
    if not instance.commerce_order_id:
        commerce_order = sync_order_commerce(instance)
        if commerce_order is not None:
            instance.commerce_order = commerce_order


@receiver(post_save, sender=TicketOrderItem, dispatch_uid="tickets.sync_order_item_commerce")
def _ticket_order_item_saved(sender, instance, **kwargs):
    # New Event checkout links the canonical line before saving the projection.
    if not instance.commerce_item_id:
        commerce_item = sync_order_item_commerce(instance)
        if commerce_item is not None:
            instance.commerce_item = commerce_item
