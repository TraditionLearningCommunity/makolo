from django.db.models.signals import post_save
from django.dispatch import receiver

from tickets.models import Ticket, TicketOrder, TicketOrderStatus, TicketWaitlistEntry

from .legacy_sync import sync_ticket_order_contact_compat
from .services import (
    confirm_campaign_attribution,
    reverse_campaign_attribution,
    sync_contact_from_ticket,
    sync_contact_from_waitlist,
)


@receiver(post_save, sender=TicketOrder, dispatch_uid="crm.sync_ticket_order_contact")
def sync_ticket_order_contact(sender, instance, **kwargs):
    sync_ticket_order_contact_compat(instance)


@receiver(post_save, sender=TicketOrder, dispatch_uid="crm.sync_campaign_order_attribution")
def sync_campaign_order_attribution(sender, instance, **kwargs):
    if instance.status == TicketOrderStatus.CONFIRMED:
        confirm_campaign_attribution(order=instance)
    elif instance.status in {TicketOrderStatus.CANCELLED, TicketOrderStatus.EXPIRED}:
        reverse_campaign_attribution(order=instance)


@receiver(post_save, sender=Ticket, dispatch_uid="crm.sync_ticket_contact")
def sync_ticket_contact(sender, instance, **kwargs):
    sync_contact_from_ticket(instance)


@receiver(post_save, sender=TicketWaitlistEntry, dispatch_uid="crm.sync_waitlist_contact")
def sync_waitlist_contact(sender, instance, **kwargs):
    sync_contact_from_waitlist(instance)
