from commerce.models import CommerceOrder, CommerceOrderStatus
from domain_events.contracts import DomainEventType
from domain_events.registry import register_consumer

from .services import issue_transport_ticket_for_order


def consume_transport_payment(event):
    if event.event_type != DomainEventType.PAYMENT_SUCCEEDED:
        return None
    order_id = (event.payload or {}).get("commerce_order_id")
    if not order_id:
        return None
    order = (
        CommerceOrder.objects.select_related(
            "journey__activity",
            "journey__occurrence",
            "journey__beneficiary",
            "journey__external_beneficiary",
        )
        .filter(pk=order_id, status=CommerceOrderStatus.CONFIRMED)
        .first()
    )
    if order is None:
        return None
    try:
        order.journey.activity.transport_service
    except Exception:
        return None
    return issue_transport_ticket_for_order(order=order)


register_consumer(
    "transport.payment-fulfillment",
    consume_transport_payment,
    event_types={DomainEventType.PAYMENT_SUCCEEDED},
)
