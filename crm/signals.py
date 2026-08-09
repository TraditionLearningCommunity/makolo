from django.db.models.signals import post_save
from django.dispatch import receiver

from tickets.models import Ticket, TicketOrder, TicketWaitlistEntry

from .services import sync_contact_from_order, sync_contact_from_ticket, sync_contact_from_waitlist


@receiver(post_save, sender=TicketOrder, dispatch_uid="crm.sync_ticket_order_contact")
def sync_ticket_order_contact(sender, instance, **kwargs):
    sync_contact_from_order(instance)


@receiver(post_save, sender=Ticket, dispatch_uid="crm.sync_ticket_contact")
def sync_ticket_contact(sender, instance, **kwargs):
    sync_contact_from_ticket(instance)


@receiver(post_save, sender=TicketWaitlistEntry, dispatch_uid="crm.sync_waitlist_contact")
def sync_waitlist_contact(sender, instance, **kwargs):
    sync_contact_from_waitlist(instance)
