"""Project canonical CommerceOrder transitions to the Event compatibility row.

Downstream legacy integrations still subscribe to TicketOrder post_save during
Task 9. CommerceOrder remains authoritative; this receiver only refreshes the
Event projection and emits the established compatibility signal surface.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from commerce.models import CommerceOrder, CommerceOrderStatus

from .models import TicketOrder, TicketOrderStatus


_STATUS_MAP = {
    CommerceOrderStatus.DRAFT: TicketOrderStatus.PENDING,
    CommerceOrderStatus.PENDING: TicketOrderStatus.PENDING,
    CommerceOrderStatus.CONFIRMED: TicketOrderStatus.CONFIRMED,
    CommerceOrderStatus.CANCELLED: TicketOrderStatus.CANCELLED,
    CommerceOrderStatus.EXPIRED: TicketOrderStatus.EXPIRED,
    CommerceOrderStatus.REFUNDED: TicketOrderStatus.CANCELLED,
}


@receiver(post_save, sender=CommerceOrder, dispatch_uid="tickets.project_commerce_order")
def project_commerce_order(sender, instance, **kwargs):
    order = TicketOrder.objects.filter(commerce_order=instance).first()
    if order is None:
        return
    order.status = _STATUS_MAP[instance.status]
    order.total_amount = instance.total
    order.currency = instance.currency
    order.expires_at = instance.expires_at
    order.confirmed_at = instance.confirmed_at
    order.cancelled_at = instance.cancelled_at
    order.save(
        update_fields=[
            "status",
            "total_amount",
            "currency",
            "expires_at",
            "confirmed_at",
            "cancelled_at",
            "updated_at",
        ]
    )
