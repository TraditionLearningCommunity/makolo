from django.db import transaction

from commerce.models import CommerceOrder, CommerceOrderStatus
from commerce.services import confirm_order

from .models import Payment, PaymentStatus


@transaction.atomic
def sync_payment_commerce(payment):
    """Synchronize Payment's canonical Commerce projection explicitly from services."""
    payment = (
        Payment.objects.select_for_update(of=("self",))
        .select_related("order__commerce_order", "commerce_order")
        .order_by()
        .get(pk=payment.pk)
    )
    commerce_order = payment.commerce_order
    if commerce_order is None and payment.order_id:
        commerce_order = payment.order.commerce_order
        if commerce_order is None:
            from tickets.commerce_capacity_bridge import sync_order_commerce

            commerce_order = sync_order_commerce(payment.order)
    if commerce_order is None:
        return None
    if payment.commerce_order_id != commerce_order.pk:
        Payment.objects.filter(pk=payment.pk).update(commerce_order=commerce_order)
        payment.commerce_order = commerce_order
    if payment.status == PaymentStatus.SUCCEEDED:
        confirm_order(order=commerce_order, payment_verified=True)
    elif payment.status == PaymentStatus.REFUNDED and commerce_order.status != CommerceOrderStatus.REFUNDED:
        # Payment owns provider/refund truth. This remains only a commercial
        # projection; Capacity release is an explicit policy elsewhere.
        CommerceOrder.objects.filter(pk=commerce_order.pk).update(status=CommerceOrderStatus.REFUNDED)
    return commerce_order
