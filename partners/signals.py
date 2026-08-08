from django.db.models.signals import post_save
from django.dispatch import receiver

from tickets.models import TicketOrder, TicketOrderStatus

from .services import confirm_order_attribution, reverse_order_attribution


@receiver(post_save, sender=TicketOrder, dispatch_uid="partners.sync_order_attribution")
def sync_order_attribution(sender, instance, **kwargs):
    if instance.status == TicketOrderStatus.CONFIRMED:
        confirm_order_attribution(order=instance)
    elif instance.status in {TicketOrderStatus.CANCELLED, TicketOrderStatus.EXPIRED}:
        reverse_order_attribution(order=instance)
