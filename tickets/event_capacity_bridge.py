"""Enforce the Event-wide capacity through canonical Capacity reservations.

Each ticket line already reserves its TicketType CapacityPool through Commerce.
This bridge adds the independent Event-wide pool created from ``Event.capacity``
so several ticket types cannot collectively oversell one Occurrence.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from capacity.models import CapacityPool, CapacityReservationStatus
from capacity.services import commit_capacity, expire_capacity, release_capacity, reserve_capacity
from commerce.models import CommerceOrder, CommerceOrderStatus

from .models import TicketOrder, TicketOrderItem, TicketOrderStatus


_TERMINAL_RELEASE_STATUSES = {
    CommerceOrderStatus.CANCELLED,
    CommerceOrderStatus.REFUNDED,
}


def _canonical_status(order):
    if order.commerce_order_id:
        return order.commerce_order.status
    return {
        TicketOrderStatus.PENDING: CommerceOrderStatus.PENDING,
        TicketOrderStatus.CONFIRMED: CommerceOrderStatus.CONFIRMED,
        TicketOrderStatus.CANCELLED: CommerceOrderStatus.CANCELLED,
        TicketOrderStatus.EXPIRED: CommerceOrderStatus.EXPIRED,
    }[order.status]


def _event_capacity_pool(order):
    return CapacityPool.objects.filter(
        activity_id=order.event.activity_id,
        occurrence_id=order.event.primary_occurrence.pk if order.event.primary_occurrence else None,
        source_key=f"event:{order.event_id}:capacity",
    ).first()


def _reservation_source(item):
    return f"event-ticket-item:{item.pk}"


def _transition_reservation(reservation, status):
    if status == CommerceOrderStatus.CONFIRMED:
        if reservation.status == CapacityReservationStatus.HELD:
            return commit_capacity(reservation=reservation)
        return reservation
    if status in _TERMINAL_RELEASE_STATUSES:
        return release_capacity(reservation=reservation, allow_committed=True)
    if status == CommerceOrderStatus.EXPIRED:
        if reservation.status != CapacityReservationStatus.HELD:
            return release_capacity(reservation=reservation, allow_committed=True)
        now = timezone.now()
        if reservation.expires_at and reservation.expires_at <= now:
            return expire_capacity(reservation=reservation, now=now)
        return release_capacity(reservation=reservation, now=now)
    return reservation


def sync_event_capacity_for_item(item, *, status=None):
    item = TicketOrderItem.objects.select_related(
        "order__event__activity",
        "order__journey",
        "order__commerce_order",
    ).get(pk=item.pk)
    order = item.order
    if not order.journey_id:
        return None
    pool = _event_capacity_pool(order)
    if pool is None:
        return None

    status = status or _canonical_status(order)
    reservation = pool.reservations.filter(
        journey_id=order.journey_id,
        source_key=_reservation_source(item),
    ).first()
    if reservation is None:
        if status in _TERMINAL_RELEASE_STATUSES or status == CommerceOrderStatus.EXPIRED:
            return None
        reservation = reserve_capacity(
            pool=pool,
            journey=order.journey,
            quantity=item.quantity,
            expires_at=order.expires_at if status == CommerceOrderStatus.PENDING else None,
            source_key=_reservation_source(item),
        )
    return _transition_reservation(reservation, status)


@receiver(post_save, sender=TicketOrderItem, dispatch_uid="tickets.reserve_event_capacity")
def reserve_event_capacity(sender, instance, **kwargs):
    sync_event_capacity_for_item(instance)


@receiver(post_save, sender=CommerceOrder, dispatch_uid="tickets.transition_event_capacity")
def transition_event_capacity(sender, instance, **kwargs):
    order = TicketOrder.objects.filter(commerce_order=instance).first()
    if order is None:
        return
    for item in order.items.all().order_by("created_at", "id"):
        sync_event_capacity_for_item(item, status=instance.status)
