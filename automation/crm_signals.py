from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from organizations.models import OrganizationFollow
from tickets.models import Ticket, TicketOrder, TicketOrderStatus, TicketStatus, TicketWaitlistEntry

from .crm_services import (
    emit_checkin_trigger,
    emit_follow_trigger,
    emit_order_trigger,
    emit_waitlist_trigger,
)
from .models import CRMWorkflowTrigger


@receiver(post_save, sender=OrganizationFollow, dispatch_uid="automation.crm_follow_trigger")
def crm_follow_trigger(sender, instance, created, **kwargs):
    if not created:
        return
    follow_id = instance.pk
    transaction.on_commit(lambda: emit_follow_trigger(follow_id))


@receiver(post_save, sender=TicketOrder, dispatch_uid="automation.crm_order_trigger")
def crm_order_trigger(sender, instance, **kwargs):
    if instance.status == TicketOrderStatus.CONFIRMED:
        order_id = instance.pk
        transaction.on_commit(
            lambda: emit_order_trigger(order_id, CRMWorkflowTrigger.ORDER_CONFIRMED)
        )
    elif instance.status == TicketOrderStatus.EXPIRED:
        order_id = instance.pk
        transaction.on_commit(
            lambda: emit_order_trigger(order_id, CRMWorkflowTrigger.ORDER_EXPIRED)
        )


@receiver(post_save, sender=TicketWaitlistEntry, dispatch_uid="automation.crm_waitlist_trigger")
def crm_waitlist_trigger(sender, instance, created, **kwargs):
    if not created:
        return
    waitlist_id = instance.pk
    transaction.on_commit(lambda: emit_waitlist_trigger(waitlist_id))


@receiver(post_save, sender=Ticket, dispatch_uid="automation.crm_checkin_trigger")
def crm_checkin_trigger(sender, instance, **kwargs):
    if instance.status != TicketStatus.USED:
        return
    ticket_id = instance.pk
    transaction.on_commit(lambda: emit_checkin_trigger(ticket_id))
