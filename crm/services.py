from datetime import timedelta

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from accounts.models import NotificationPreference
from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification
from tickets.models import Ticket, TicketOrder, TicketWaitlistEntry

from .models import (
    AudienceSegment,
    CampaignRecipient,
    CampaignRecipientStatus,
    CommunicationCampaign,
    CommunicationCampaignStatus,
    CommunicationKind,
    ContactSource,
    CRMContact,
    CRMContactNote,
    MarketingConsent,
)
from .permissions import user_can_manage_crm
from .selectors import audience_contacts


UNSUBSCRIBE_SIGNING_SALT = "makolo.crm.unsubscribe"


def _public_url(path: str) -> str:
    if path.startswith("http://") or path.startswith("https://"):
        return path
    base = getattr(settings, "MAKOLO_PUBLIC_BASE_URL", "").rstrip("/")
    return f"{base}/{path.lstrip('/')}" if base else path


def _user_marketing_opt_in(user) -> bool:
    if not user:
        return False
    preference = NotificationPreference.objects.filter(user=user).first()
    return bool(preference and preference.email_notifications and preference.marketing_notifications)


def _upsert_contact(
    *,
    organization,
    email,
    user=None,
    name="",
    phone="",
    source=ContactSource.TICKET_ORDER,
    seen_at=None,
):
    email = (email or "").strip().lower()
    if not email:
        return None
    seen_at = seen_at or timezone.now()
    contact, created = CRMContact.objects.get_or_create(
        organization=organization,
        email=email,
        defaults={
            "user": user,
            "name": (name or "").strip(),
            "phone": (phone or "").strip(),
            "source": source,
            "first_seen_at": seen_at,
            "last_seen_at": seen_at,
        },
    )
    changed = []
    if user and contact.user_id != user.pk:
        contact.user = user
        changed.append("user")
    if name and (created or not contact.name):
        contact.name = name.strip()
        changed.append("name")
    if phone and (created or not contact.phone):
        contact.phone = phone.strip()
        changed.append("phone")
    if seen_at and seen_at > contact.last_seen_at:
        contact.last_seen_at = seen_at
        changed.append("last_seen_at")
    if (
        contact.marketing_consent == MarketingConsent.UNKNOWN
        and user
        and _user_marketing_opt_in(user)
    ):
        contact.marketing_consent = MarketingConsent.SUBSCRIBED
        contact.consent_source = "account_notification_preferences"
        contact.consent_updated_at = timezone.now()
        changed.extend(["marketing_consent", "consent_source", "consent_updated_at"])
    if changed:
        contact.save(update_fields=list(dict.fromkeys(changed + ["updated_at"])))
    return contact


def sync_contact_from_order(order: TicketOrder):
    organization = getattr(order.event, "organization", None)
    if not organization:
        return None
    return _upsert_contact(
        organization=organization,
        email=order.customer_email,
        user=order.buyer,
        name=order.customer_name,
        phone=getattr(order.buyer, "phone", "") if order.buyer_id else "",
        source=ContactSource.TICKET_ORDER,
        seen_at=order.created_at or timezone.now(),
    )


def sync_contact_from_ticket(ticket: Ticket):
    organization = getattr(ticket.event, "organization", None)
    if not organization:
        return None
    return _upsert_contact(
        organization=organization,
        email=ticket.holder_email,
        user=ticket.owner,
        name=ticket.holder_name,
        phone=getattr(ticket.owner, "phone", "") if ticket.owner_id else "",
        source=ContactSource.TICKET,
        seen_at=ticket.issued_at or timezone.now(),
    )


def sync_contact_from_waitlist(entry: TicketWaitlistEntry):
    organization = getattr(entry.ticket_type.event, "organization", None)
    if not organization:
        return None
    user = entry.user
    return _upsert_contact(
        organization=organization,
        email=user.email,
        user=user,
        name=user.full_name or user.username,
        phone=user.phone or "",
        source=ContactSource.WAITLIST,
        seen_at=entry.created_at or timezone.now(),
    )


def sync_organization_contacts(organization):
    synced = 0
    orders = TicketOrder.objects.filter(event__organization=organization).select_related("event", "buyer")
    for order in orders.iterator():
        if sync_contact_from_order(order):
            synced += 1
    tickets = Ticket.objects.filter(event__organization=organization).select_related("event", "owner")
    for ticket in tickets.iterator():
        if sync_contact_from_ticket(ticket):
            synced += 1
    waitlist = TicketWaitlistEntry.objects.filter(
        ticket_type__event__organization=organization
    ).select_related("ticket_type__event", "user")
    for entry in waitlist.iterator():
        if sync_contact_from_waitlist(entry):
            synced += 1
    return synced


@transaction.atomic
def set_marketing_consent(*, contact: CRMContact, actor, subscribed: bool, source: str):
    contact = CRMContact.objects.select_for_update().select_related("organization", "user").get(pk=contact.pk)
    if not user_can_manage_crm(actor, contact.organization):
        raise PermissionDenied("Vous n’avez pas le droit de modifier le consentement CRM.")
    source = (source or "").strip()
    if subscribed and not source:
        raise ValidationError("Une source de consentement est requise pour abonner un contact.")
    contact.marketing_consent = MarketingConsent.SUBSCRIBED if subscribed else MarketingConsent.UNSUBSCRIBED
    contact.consent_source = source or "crm_manual_unsubscribe"
    contact.consent_updated_at = timezone.now()
    contact.save(update_fields=["marketing_consent", "consent_source", "consent_updated_at", "updated_at"])
    if contact.user_id:
        preference, _ = NotificationPreference.objects.get_or_create(user=contact.user)
        preference.marketing_notifications = bool(subscribed)
        preference.save(update_fields=["marketing_notifications", "updated_at"])
    return contact


@transaction.atomic
def add_contact_note(*, contact: CRMContact, actor, body: str):
    contact = CRMContact.objects.select_related("organization").get(pk=contact.pk)
    if not user_can_manage_crm(actor, contact.organization):
        raise PermissionDenied("Vous n’avez pas le droit d’ajouter une note CRM.")
    body = (body or "").strip()
    if not body:
        raise ValidationError("La note ne peut pas être vide.")
    return CRMContactNote.objects.create(contact=contact, author=actor, body=body)


@transaction.atomic
def create_segment(*, organization, actor, **data):
    if not user_can_manage_crm(actor, organization):
        raise PermissionDenied("Vous n’avez pas le droit de créer un segment CRM.")
    segment = AudienceSegment(organization=organization, created_by=actor, **data)
    segment.full_clean()
    segment.save()
    return segment


@transaction.atomic
def create_campaign(*, organization, actor, **data):
    if not user_can_manage_crm(actor, organization):
        raise PermissionDenied("Vous n’avez pas le droit de créer une campagne CRM.")
    campaign = CommunicationCampaign(organization=organization, created_by=actor, **data)
    campaign.full_clean()
    campaign.save()
    return campaign


@transaction.atomic
def schedule_campaign(*, campaign: CommunicationCampaign, actor, scheduled_at):
    campaign = CommunicationCampaign.objects.select_for_update().select_related("organization").get(pk=campaign.pk)
    if not user_can_manage_crm(actor, campaign.organization):
        raise PermissionDenied("Vous n’avez pas le droit de planifier cette campagne.")
    if campaign.status != CommunicationCampaignStatus.DRAFT:
        raise ValidationError("Seule une campagne brouillon peut être planifiée.")
    if scheduled_at <= timezone.now():
        raise ValidationError("La date de planification doit être dans le futur.")
    campaign.status = CommunicationCampaignStatus.SCHEDULED
    campaign.scheduled_at = scheduled_at
    campaign.save(update_fields=["status", "scheduled_at", "updated_at"])
    return campaign


def _snapshot_campaign(campaign: CommunicationCampaign):
    sync_organization_contacts(campaign.organization)
    contacts = audience_contacts(campaign.segment).only("id", "user_id", "email", "name")
    created = 0
    for contact in contacts.iterator():
        _, was_created = CampaignRecipient.objects.get_or_create(
            campaign=campaign,
            contact=contact,
            defaults={
                "user_id": contact.user_id,
                "email": contact.email,
                "name": contact.name,
                "scheduled_for": timezone.now(),
            },
        )
        if was_created:
            created += 1
    return created


@transaction.atomic
def launch_campaign(*, campaign: CommunicationCampaign, actor=None):
    campaign = (
        CommunicationCampaign.objects.select_for_update()
        .select_related("organization", "segment", "event")
        .get(pk=campaign.pk)
    )
    if actor is not None and not user_can_manage_crm(actor, campaign.organization):
        raise PermissionDenied("Vous n’avez pas le droit d’envoyer cette campagne.")
    if campaign.status == CommunicationCampaignStatus.SENDING:
        return campaign
    if campaign.status in {CommunicationCampaignStatus.SENT, CommunicationCampaignStatus.CANCELLED}:
        raise ValidationError("Cette campagne ne peut plus être envoyée.")
    if campaign.kind == CommunicationKind.EVENT_UPDATE and not campaign.event_id:
        raise ValidationError("Une campagne événementielle nécessite un événement.")

    _snapshot_campaign(campaign)
    now = timezone.now()
    campaign.status = CommunicationCampaignStatus.SENDING
    campaign.started_at = campaign.started_at or now
    campaign.scheduled_at = campaign.scheduled_at or now
    campaign.save(update_fields=["status", "started_at", "scheduled_at", "updated_at"])
    if not campaign.recipients.exists():
        campaign.status = CommunicationCampaignStatus.SENT
        campaign.completed_at = now
        campaign.save(update_fields=["status", "completed_at", "updated_at"])
    return campaign


@transaction.atomic
def cancel_campaign(*, campaign: CommunicationCampaign, actor):
    campaign = CommunicationCampaign.objects.select_for_update().select_related("organization").get(pk=campaign.pk)
    if not user_can_manage_crm(actor, campaign.organization):
        raise PermissionDenied("Vous n’avez pas le droit d’annuler ce paiement de commissions.")
    if campaign.status == CommunicationCampaignStatus.SENT:
        raise ValidationError("Une campagne déjà envoyée ne peut pas être annulée.")
    if campaign.status == CommunicationCampaignStatus.CANCELLED:
        return campaign
    now = timezone.now()
    campaign.status = CommunicationCampaignStatus.CANCELLED
    campaign.cancelled_at = now
    campaign.save(update_fields=["status", "cancelled_at", "updated_at"])
    campaign.recipients.filter(status=CampaignRecipientStatus.QUEUED).update(
        status=CampaignRecipientStatus.SKIPPED,
        skipped_reason="Campagne annulée.",
        updated_at=now,
    )
    return campaign


def _recipient_allowed(recipient: CampaignRecipient):
    campaign = recipient.campaign
    contact = recipient.contact
    if campaign.kind == CommunicationKind.MARKETING:
        if contact.marketing_consent != MarketingConsent.SUBSCRIBED:
            return False, "Le contact n’a pas donné de consentement marketing actif."
        if recipient.user_id:
            preference = NotificationPreference.objects.filter(user_id=recipient.user_id).first()
            if preference and (not preference.email_notifications or not preference.marketing_notifications):
                return False, "Les préférences du compte désactivent les communications marketing."
    elif recipient.user_id:
        preference = NotificationPreference.objects.filter(user_id=recipient.user_id).first()
        if preference and (not preference.email_notifications or not preference.event_notifications):
            return False, "Les préférences du compte désactivent les communications événementielles."
    return True, ""


def campaign_unsubscribe_token(recipient: CampaignRecipient):
    return signing.dumps(
        {"contact_id": str(recipient.contact_id), "campaign_id": str(recipient.campaign_id)},
        salt=UNSUBSCRIBE_SIGNING_SALT,
        compress=True,
    )


def _claim_recipient(recipient_id):
    with transaction.atomic():
        recipient = (
            CampaignRecipient.objects.select_for_update()
            .select_related("campaign", "campaign__event", "contact", "user")
            .get(pk=recipient_id)
        )
        if recipient.status != CampaignRecipientStatus.QUEUED:
            return None
        if recipient.campaign.status != CommunicationCampaignStatus.SENDING:
            return None
        if recipient.scheduled_for > timezone.now():
            return None
        recipient.status = CampaignRecipientStatus.PROCESSING
        recipient.attempts += 1
        recipient.last_error = ""
        recipient.save(update_fields=["status", "attempts", "last_error", "updated_at"])
        return recipient


def dispatch_campaign_recipient(recipient_id):
    recipient = _claim_recipient(recipient_id)
    if not recipient:
        return "ignored"

    allowed, reason = _recipient_allowed(recipient)
    if not allowed:
        CampaignRecipient.objects.filter(pk=recipient.pk).update(
            status=CampaignRecipientStatus.SKIPPED,
            skipped_reason=reason,
            updated_at=timezone.now(),
        )
        return "skipped"

    campaign = recipient.campaign
    unsubscribe_url = ""
    if campaign.kind == CommunicationKind.MARKETING:
        token = campaign_unsubscribe_token(recipient)
        unsubscribe_url = _public_url(reverse("crm:unsubscribe", kwargs={"token": token}))
    context = {
        "campaign": campaign,
        "recipient": recipient,
        "contact": recipient.contact,
        "unsubscribe_url": unsubscribe_url,
        "cta_url": campaign.cta_url,
    }
    text_body = render_to_string("crm/email/campaign.txt", context)
    html_body = render_to_string("crm/email/campaign.html", context)

    try:
        email = EmailMultiAlternatives(
            subject=campaign.subject,
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient.email],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=False)
    except Exception as exc:
        recipient.refresh_from_db(fields=["attempts", "max_attempts"])
        terminal = recipient.attempts >= recipient.max_attempts
        now = timezone.now()
        CampaignRecipient.objects.filter(pk=recipient.pk).update(
            status=CampaignRecipientStatus.FAILED if terminal else CampaignRecipientStatus.QUEUED,
            last_error=str(exc)[:1000],
            scheduled_for=now + timedelta(minutes=max(recipient.attempts, 1) * 5),
            updated_at=now,
        )
        return "failed" if terminal else "retry"

    now = timezone.now()
    CampaignRecipient.objects.filter(pk=recipient.pk).update(
        status=CampaignRecipientStatus.SENT,
        sent_at=now,
        last_error="",
        updated_at=now,
    )
    if recipient.user_id:
        try:
            create_notification(
                recipient=recipient.user,
                kind=NotificationKind.SYSTEM,
                category=(
                    NotificationCategory.MARKETING
                    if campaign.kind == CommunicationKind.MARKETING
                    else NotificationCategory.EVENT
                ),
                title=campaign.subject,
                message=campaign.body,
                action_url=campaign.cta_url,
                dedup_key=f"crm-campaign:{campaign.pk}:{recipient.user_id}",
                metadata={"campaign_id": str(campaign.pk), "event_id": str(campaign.event_id) if campaign.event_id else None},
                queue_email=False,
            )
        except Exception:
            pass
    return "sent"


def recover_stale_campaign_recipients(*, now=None, stale_minutes=15):
    now = now or timezone.now()
    cutoff = now - timedelta(minutes=stale_minutes)
    return CampaignRecipient.objects.filter(
        status=CampaignRecipientStatus.PROCESSING,
        updated_at__lt=cutoff,
        campaign__status=CommunicationCampaignStatus.SENDING,
    ).update(
        status=CampaignRecipientStatus.QUEUED,
        scheduled_for=now,
        last_error="Reprise automatique après interruption du worker.",
        updated_at=now,
    )


def finalize_campaigns(*, now=None):
    now = now or timezone.now()
    completed = 0
    for campaign in CommunicationCampaign.objects.filter(status=CommunicationCampaignStatus.SENDING):
        if campaign.recipients.filter(
            status__in=[CampaignRecipientStatus.QUEUED, CampaignRecipientStatus.PROCESSING]
        ).exists():
            continue
        campaign.status = CommunicationCampaignStatus.SENT
        campaign.completed_at = now
        campaign.save(update_fields=["status", "completed_at", "updated_at"])
        completed += 1
    return completed


def process_due_campaigns(*, now=None, campaign_limit=20, recipient_limit=100):
    reference_now = now or timezone.now()
    launched = 0
    due = list(
        CommunicationCampaign.objects.filter(
            status=CommunicationCampaignStatus.SCHEDULED,
            scheduled_at__lte=reference_now,
        ).order_by("scheduled_at")[:campaign_limit]
    )
    for campaign in due:
        launch_campaign(campaign=campaign)
        launched += 1

    # A campaign snapshot timestamps its recipients during launch. Refresh the
    # dispatch cutoff so recipients created a few milliseconds after the cycle
    # started can still be processed in this same Autopilot iteration. When a
    # caller supplies a future reference time (tests/operations), preserve it.
    dispatch_now = max(reference_now, timezone.now())
    recovered = recover_stale_campaign_recipients(now=dispatch_now)
    recipient_ids = list(
        CampaignRecipient.objects.filter(
            status=CampaignRecipientStatus.QUEUED,
            scheduled_for__lte=dispatch_now,
            campaign__status=CommunicationCampaignStatus.SENDING,
        ).order_by("scheduled_for", "created_at").values_list("pk", flat=True)[:recipient_limit]
    )
    outcomes = {"sent": 0, "retry": 0, "failed": 0, "skipped": 0, "ignored": 0}
    for recipient_id in recipient_ids:
        outcome = dispatch_campaign_recipient(recipient_id)
        outcomes[outcome] = outcomes.get(outcome, 0) + 1
    completed = finalize_campaigns(now=dispatch_now)
    return {
        "launched": launched,
        "recovered": recovered,
        "completed": completed,
        "recipients": outcomes,
    }


@transaction.atomic
def unsubscribe_from_token(token: str):
    try:
        payload = signing.loads(token, salt=UNSUBSCRIBE_SIGNING_SALT)
    except signing.BadSignature as exc:
        raise ValidationError("Lien de désabonnement invalide.") from exc
    contact = CRMContact.objects.select_for_update().select_related("user").filter(
        pk=payload.get("contact_id")
    ).first()
    if not contact:
        raise ValidationError("Contact CRM introuvable.")
    contact.marketing_consent = MarketingConsent.UNSUBSCRIBED
    contact.consent_source = "campaign_unsubscribe"
    contact.consent_updated_at = timezone.now()
    contact.save(update_fields=["marketing_consent", "consent_source", "consent_updated_at", "updated_at"])
    if contact.user_id:
        preference, _ = NotificationPreference.objects.get_or_create(user=contact.user)
        preference.marketing_notifications = False
        preference.save(update_fields=["marketing_notifications", "updated_at"])
    return contact
