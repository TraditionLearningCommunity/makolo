"""Keep the Event Ticket representation aligned with canonical Access state."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from access.models import Access, AccessStatus, AccessUse, AccessUseResult
from access.services import cancel_access, revoke_access

from .models import Ticket, TicketStatus


_ACCESS_TO_TICKET = {
    AccessStatus.CANCELLED: TicketStatus.CANCELLED,
    AccessStatus.REVOKED: TicketStatus.REFUNDED,
    AccessStatus.EXPIRED: TicketStatus.CANCELLED,
    AccessStatus.TRANSFERRED: TicketStatus.CANCELLED,
}


@receiver(post_save, sender=AccessUse, dispatch_uid="tickets.project_access_use")
def project_access_use(sender, instance, **kwargs):
    if instance.result != AccessUseResult.ACCEPTED:
        return
    ticket = Ticket.objects.filter(access=instance.access).first()
    if ticket is None:
        return
    ticket.status = TicketStatus.USED
    ticket.used_at = instance.used_at
    ticket.save(update_fields=["status", "used_at", "updated_at"])


@receiver(post_save, sender=Access, dispatch_uid="tickets.project_access_status")
def project_access_status(sender, instance, **kwargs):
    target = _ACCESS_TO_TICKET.get(instance.status)
    if target is None:
        return
    ticket = Ticket.objects.filter(access=instance).first()
    if ticket is None or ticket.status == target:
        return
    ticket.status = target
    if target in {TicketStatus.CANCELLED, TicketStatus.REFUNDED}:
        ticket.cancelled_at = instance.updated_at
        ticket.save(update_fields=["status", "cancelled_at", "updated_at"])
    else:
        ticket.save(update_fields=["status", "updated_at"])


@receiver(post_save, sender=Ticket, dispatch_uid="tickets.project_legacy_ticket_status")
def project_legacy_ticket_status(sender, instance, **kwargs):
    """Honor an explicit legacy cancellation without making Ticket canonical."""
    if not instance.access_id:
        return
    if instance.status == TicketStatus.CANCELLED and instance.access.status != AccessStatus.CANCELLED:
        cancel_access(access=instance.access, actor=None)
    elif instance.status == TicketStatus.REFUNDED and instance.access.status != AccessStatus.REVOKED:
        revoke_access(access=instance.access, actor=None)
