from django.contrib.auth import get_user_model
from django.db import transaction

from activities.models import Activity
from commerce.models import CommerceOrder
from domain_events.contracts import DomainEventType
from domain_events.registry import register_consumer

from .canonical_models import CRMInteraction, CRMInteractionType
from .models import CRMContact, MarketingConsent


CONSUMER_NAME = "crm.system"
CRM_EVENT_TYPES = {
    DomainEventType.JOURNEY_SUBMITTED,
    DomainEventType.JOURNEY_CONFIRMED,
    DomainEventType.JOURNEY_FULFILLED,
    DomainEventType.ACCESS_ISSUED,
    DomainEventType.ACCESS_USED,
    DomainEventType.COMMERCE_ORDER_CONFIRMED,
    DomainEventType.PAYMENT_SUCCEEDED,
}


def _profile_id(domain_event):
    payload = domain_event.payload or {}
    if domain_event.event_type.startswith("commerce.order"):
        return payload.get("buyer_id") or payload.get("beneficiary_id")
    if domain_event.event_type.startswith("payment."):
        return payload.get("buyer_id") or payload.get("beneficiary_id")
    return payload.get("beneficiary_id") or payload.get("buyer_id")


def _commercial_order(domain_event):
    payload = domain_event.payload or {}
    order_id = payload.get("commerce_order_id")
    if not order_id:
        return None
    return CommerceOrder.objects.select_related("payee_space", "journey__beneficiary").filter(pk=order_id).first()


def _space_id(domain_event, commerce_order=None):
    if commerce_order is not None:
        return commerce_order.payee_space_id
    return domain_event.space_id


def _interaction_type(event_type):
    allowed = {choice for choice, _label in CRMInteractionType.choices}
    return event_type if event_type in allowed else None


def _contact_for_profile(*, organization_id, profile, occurred_at):
    contact = CRMContact.objects.filter(organization_id=organization_id, user=profile).first()
    email = (profile.email or "").strip().lower()
    if contact is None and email:
        candidate = CRMContact.objects.filter(organization_id=organization_id, email=email).first()
        if candidate is not None and candidate.user_id in {None, profile.pk}:
            candidate.user = profile
            candidate.save(update_fields=["user", "updated_at"])
            contact = candidate
    if contact is None:
        if not email:
            return None
        contact = CRMContact.objects.create(
            organization_id=organization_id,
            user=profile,
            email=email,
            name=profile.get_full_name().strip(),
            source="manual",
            marketing_consent=MarketingConsent.UNKNOWN,
            first_seen_at=occurred_at,
            last_seen_at=occurred_at,
        )
        return contact

    changed = []
    if contact.last_seen_at < occurred_at:
        contact.last_seen_at = occurred_at
        changed.append("last_seen_at")
    if contact.first_seen_at > occurred_at:
        contact.first_seen_at = occurred_at
        changed.append("first_seen_at")
    if email and contact.email != email and not CRMContact.objects.filter(
        organization_id=organization_id, email=email
    ).exclude(pk=contact.pk).exists():
        contact.email = email
        changed.append("email")
    profile_name = profile.get_full_name().strip()
    if profile_name and contact.name != profile_name:
        contact.name = profile_name
        changed.append("name")
    if changed:
        changed.append("updated_at")
        contact.save(update_fields=changed)
    return contact


@transaction.atomic
def consume_crm_event(domain_event):
    interaction_type = _interaction_type(domain_event.event_type)
    if interaction_type is None:
        return

    commerce_order = _commercial_order(domain_event)
    profile_id = _profile_id(domain_event)
    if profile_id is None and commerce_order is not None:
        profile_id = commerce_order.buyer_id or commerce_order.journey.beneficiary_id
    if profile_id is None:
        return

    profile = get_user_model().objects.filter(pk=profile_id).first()
    organization_id = _space_id(domain_event, commerce_order=commerce_order)
    if profile is None or organization_id is None:
        return

    contact = _contact_for_profile(
        organization_id=organization_id,
        profile=profile,
        occurred_at=domain_event.occurred_at,
    )
    if contact is None:
        return
    activity = None
    if domain_event.activity_id:
        activity = Activity.objects.filter(pk=domain_event.activity_id).first()
    CRMInteraction.objects.get_or_create(
        contact=contact,
        domain_event=domain_event,
        interaction_type=interaction_type,
        defaults={"activity": activity, "occurred_at": domain_event.occurred_at},
    )


register_consumer(CONSUMER_NAME, consume_crm_event, event_types=CRM_EVENT_TYPES)
