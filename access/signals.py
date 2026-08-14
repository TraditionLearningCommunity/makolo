import uuid

from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import AccessCredential


@receiver(
    post_save,
    sender=AccessCredential,
    dispatch_uid="access.rotate_linked_legacy_ticket_code",
)
def rotate_linked_legacy_ticket_code(sender, instance, created, **kwargs):
    """Invalidate a historical Ticket QR when Access gains a credential.

    New Tickets receive their AccessCredential before ``Ticket.access`` is linked,
    so this hook does not churn their unpublished legacy code. For a backfilled
    Ticket that already points at an Access, however, issuing or rotating a
    canonical credential also rotates ``Ticket.code``. The former signed
    Ticket QR is then invalid across every resolver, not only the Scanner.
    """
    if not created:
        return
    try:
        ticket = instance.access.ticket
    except ObjectDoesNotExist:
        return

    ticket.code = uuid.uuid4()
    ticket.save(update_fields=["code", "updated_at"])
