from django.db.models.signals import post_save
from django.dispatch import receiver

from tickets.models import Ticket, TicketOrder, TicketOrderStatus, TicketStatus

from .services import award_checkin_points, award_order_points, reverse_order_points


@receiver(post_save, sender=TicketOrder, dispatch_uid="loyalty.sync_order_points")
def sync_order_points(sender, instance, **kwargs):
    if instance.status == TicketOrderStatus.CONFIRMED:
        award_order_points(instance)
    elif instance.status in {TicketOrderStatus.CANCELLED, TicketOrderStatus.EXPIRED}:
        reverse_order_points(instance)


@receiver(post_save, sender=Ticket, dispatch_uid="loyalty.sync_checkin_points")
def sync_checkin_points(sender, instance, **kwargs):
    if instance.status == TicketStatus.USED:
        award_checkin_points(instance)
