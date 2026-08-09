from django.db.models.signals import post_save
from django.dispatch import receiver

from tickets.models import TicketOrder, TicketOrderStatus

from .services import confirm_redemption, reverse_redemption


@receiver(post_save, sender=TicketOrder, dispatch_uid="promotions.sync_order_redemption")
def sync_order_redemption(sender, instance, **kwargs):
    if instance.status == TicketOrderStatus.CONFIRMED:
        confirm_redemption(order=instance)
    elif instance.status in {TicketOrderStatus.CANCELLED, TicketOrderStatus.EXPIRED}:
        reverse_redemption(order=instance)
