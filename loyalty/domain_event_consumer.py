from access.models import AccessUse
from commerce.models import CommerceOrder
from domain_events.contracts import DomainEventType
from domain_events.registry import register_consumer

from .points import (
    award_access_use_points,
    award_commerce_order_points,
    reverse_commerce_order_points,
)


CONSUMER_NAME = "loyalty.points"
LOYALTY_EVENT_TYPES = {
    DomainEventType.COMMERCE_ORDER_CONFIRMED,
    DomainEventType.COMMERCE_ORDER_CANCELLED,
    DomainEventType.COMMERCE_ORDER_EXPIRED,
    DomainEventType.ACCESS_USED,
}


def consume_loyalty_event(domain_event):
    payload = domain_event.payload or {}
    if domain_event.event_type == DomainEventType.ACCESS_USED:
        use_id = payload.get("access_use_id")
        if not use_id:
            return
        access_use = AccessUse.objects.select_related(
            "access",
            "access__beneficiary",
            "access__activity",
            "access__activity__space",
        ).filter(pk=use_id).first()
        if access_use is not None:
            award_access_use_points(access_use)
        return

    order_id = payload.get("commerce_order_id")
    if not order_id:
        return
    order = CommerceOrder.objects.select_related(
        "buyer",
        "payee_space",
        "journey",
    ).prefetch_related("items").filter(pk=order_id).first()
    if order is None:
        return
    if domain_event.event_type == DomainEventType.COMMERCE_ORDER_CONFIRMED:
        award_commerce_order_points(order)
    else:
        reverse_commerce_order_points(order)


register_consumer(CONSUMER_NAME, consume_loyalty_event, event_types=LOYALTY_EVENT_TYPES)
