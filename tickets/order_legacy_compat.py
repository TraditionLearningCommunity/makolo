"""Narrow Event-order compatibility during the Commerce cutover.

CommerceOrder remains authoritative. This adapter preserves two historical
Event entry points until all callers use Commerce directly:

* an explicitly authorized Event manager may manually confirm a paid order;
* an expiry written on the TicketOrder projection is still enforced.

Provider callbacks continue through ``_confirm_locked_order`` and are not
patched by this adapter.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from commerce.models import CommerceOrderStatus
from events.permissions import user_can_manage_event
from journeys.models import Journey, JourneyStatus
from journeys.services import fulfill_journey

from .models import TicketOrder, TicketOrderStatus


def _compat_is_expired(order):
    now = timezone.now()
    if order.status == TicketOrderStatus.EXPIRED:
        return True
    if (
        order.status == TicketOrderStatus.PENDING
        and order.expires_at
        and now >= order.expires_at
    ):
        return True
    if order.commerce_order_id:
        return order.commerce_order.status == CommerceOrderStatus.EXPIRED or bool(
            order.commerce_order.status == CommerceOrderStatus.PENDING
            and order.commerce_order.expires_at
            and now >= order.commerce_order.expires_at
        )
    return False


def _fulfill_legacy_journey_if_needed(*, journey_id, actor):
    """Fulfill once when another canonical consumer has not already done it."""
    journey = Journey.objects.get(pk=journey_id)
    if journey.status == JourneyStatus.FULFILLED:
        return journey
    if journey.status != JourneyStatus.CONFIRMED:
        return journey
    try:
        return fulfill_journey(
            journey=journey,
            actor=actor,
            reason="event_ticket_issued",
        )
    except ValidationError:
        journey.refresh_from_db()
        if journey.status == JourneyStatus.FULFILLED:
            return journey
        raise


def install_ticket_order_legacy_compat():
    if getattr(TicketOrder, "_order_legacy_compat_installed", False):
        return

    from . import services

    canonical_expire_order = services.expire_order

    @transaction.atomic
    def confirm_event_order(*, order: TicketOrder, actor) -> TicketOrder:
        """Historical Event-manager confirmation with explicit authority.

        This is the only compatibility path that sets ``payment_verified``.
        Generic Commerce confirmation still requires a successful Payment.
        """
        order = (
            TicketOrder.objects.select_for_update(of=("self",))
            .select_related("event", "event__activity", "commerce_order", "journey")
            .get(pk=order.pk)
        )
        if not user_can_manage_event(actor, order.event):
            raise PermissionDenied("Vous ne pouvez pas confirmer cette commande.")
        if order.is_expired:
            raise ValidationError("Cette commande a expiré.")
        if not order.commerce_order_id:
            raise ValidationError("Cette commande n’a pas de CommerceOrder canonique.")

        commerce_order = services.confirm_commerce_order(
            order=order.commerce_order,
            actor=actor,
            payment_verified=True,
        )
        order = services._project_commerce_order(order, commerce_order)
        services._issue_tickets_for_order(order)
        if order.journey_id:
            _fulfill_legacy_journey_if_needed(
                journey_id=order.journey_id,
                actor=actor,
            )
        return TicketOrder.objects.get(pk=order.pk)

    @transaction.atomic
    def expire_event_order(*, order: TicketOrder) -> TicketOrder:
        """Propagate a legacy expiry timestamp before canonical expiration."""
        order = (
            TicketOrder.objects.select_for_update(of=("self",))
            .select_related("commerce_order")
            .get(pk=order.pk)
        )
        if not order.commerce_order_id or not order.expires_at:
            return canonical_expire_order(order=order)
        commerce_order = order.commerce_order
        if (
            commerce_order.status == CommerceOrderStatus.PENDING
            and (
                commerce_order.expires_at is None
                or order.expires_at < commerce_order.expires_at
            )
        ):
            commerce_order.expires_at = order.expires_at
            commerce_order.save(update_fields=["expires_at", "updated_at"])
        return canonical_expire_order(order=order)

    TicketOrder.is_expired = property(_compat_is_expired)
    services.confirm_order = confirm_event_order
    services.expire_order = expire_event_order
    TicketOrder._order_legacy_compat_installed = True
