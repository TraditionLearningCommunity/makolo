from django.contrib.auth import get_user_model
from django.db import transaction

from .models import ContactSource, CRMContact
from .services import _upsert_contact, sync_contact_from_order


@transaction.atomic
def sync_ticket_order_contact_compat(order):
    """Keep the Event/Ticket CRM bridge compatible with canonical Space/Profile identity.

    Historical TicketOrder rows may carry a customer e-mail that differs from the
    authenticated buyer's account e-mail. Once a Profile exists, that order e-mail
    is no longer contact identity: Space + Profile is. Locking the Profile also
    serializes concurrent legacy TicketOrder signals for the same canonical contact.
    Guest orders without a Profile keep the historical e-mail-based path.
    """
    organization = getattr(order.event, "organization", None)
    if not organization or not order.buyer_id:
        return sync_contact_from_order(order)

    User = get_user_model()
    user = User.objects.select_for_update().get(pk=order.buyer_id)
    existing = CRMContact.objects.filter(organization=organization, user=user).only("email").first()

    # Preserve an already-established CRM address. For the first canonical contact,
    # prefer the Profile address and only fall back to the historical order address.
    email = (existing.email if existing else "") or user.email or order.customer_email
    return _upsert_contact(
        organization=organization,
        email=email,
        user=user,
        name=order.customer_name,
        phone=getattr(user, "phone", "") or "",
        source=ContactSource.TICKET_ORDER,
        seen_at=order.created_at,
    )
