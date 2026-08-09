from django.db.models import Count, Exists, OuterRef, Q, Sum
from django.utils import timezone

from organizations.models import OrganizationFollow, OrganizationMembership
from partners.models import AttributionStatus, ReferralAttribution
from tickets.models import (
    Ticket,
    TicketOrder,
    TicketOrderStatus,
    TicketStatus,
    TicketWaitlistEntry,
    WaitlistStatus,
)

from .models import (
    AudienceKind,
    AudienceSegment,
    CampaignAttributionStatus,
    CampaignRecipientStatus,
    CommunicationCampaign,
    CRMContact,
    CRMContactFieldValue,
    MarketingConsent,
)
from .permissions import CRM_VIEW_ROLES


def _visible_organization_ids(user):
    if not getattr(user, "is_authenticated", False):
        return []
    if user.is_staff:
        return None
    return OrganizationMembership.objects.filter(
        user=user,
        is_active=True,
        role__in=CRM_VIEW_ROLES,
    ).values_list("organization_id", flat=True)


def get_contacts_visible_to(user):
    queryset = CRMContact.objects.select_related("organization", "user", "user__profile").prefetch_related(
        "tag_links__tag", "custom_values__field"
    )
    organization_ids = _visible_organization_ids(user)
    if organization_ids is None:
        return queryset
    return queryset.filter(organization_id__in=organization_ids)


def get_segments_visible_to(user):
    queryset = AudienceSegment.objects.select_related(
        "organization", "event", "ticket_type", "created_by"
    ).prefetch_related("required_tags")
    organization_ids = _visible_organization_ids(user)
    if organization_ids is None:
        return queryset
    return queryset.filter(organization_id__in=organization_ids)


def get_campaigns_visible_to(user):
    queryset = CommunicationCampaign.objects.select_related(
        "organization", "segment", "event", "template", "created_by"
    )
    organization_ids = _visible_organization_ids(user)
    if organization_ids is None:
        return queryset
    return queryset.filter(organization_id__in=organization_ids)


def _apply_contact_filters(queryset, segment: AudienceSegment):
    if segment.marketing_consent_only:
        queryset = queryset.filter(marketing_consent=MarketingConsent.SUBSCRIBED)
    if segment.city:
        queryset = queryset.filter(user__profile__city__iexact=segment.city.strip())
    if segment.country:
        queryset = queryset.filter(user__profile__country__iexact=segment.country.strip())

    for tag in segment.required_tags.all():
        queryset = queryset.filter(tag_links__tag=tag)

    for field_key, expected_value in (segment.custom_filters or {}).items():
        values = CRMContactFieldValue.objects.filter(
            contact_id=OuterRef("pk"),
            field__organization=segment.organization,
            field__key=field_key,
            field__is_active=True,
            value=expected_value,
        )
        queryset = queryset.annotate(**{f"_crm_field_{str(field_key).replace('-', '_')}": Exists(values)}).filter(
            **{f"_crm_field_{str(field_key).replace('-', '_')}": True}
        )
    return queryset


def audience_contacts(segment: AudienceSegment):
    queryset = CRMContact.objects.filter(organization=segment.organization).select_related(
        "user", "user__profile"
    )
    queryset = _apply_contact_filters(queryset, segment)

    if segment.audience_kind == AudienceKind.ALL:
        return queryset.distinct()

    if segment.audience_kind == AudienceKind.FOLLOWERS:
        follows = OrganizationFollow.objects.filter(
            organization=segment.organization,
            user_id=OuterRef("user_id"),
        )
        return queryset.annotate(_crm_match=Exists(follows)).filter(_crm_match=True).distinct()

    event = segment.event
    if not event:
        return queryset.none()

    contact_match = Q(customer_email=OuterRef("email")) | Q(buyer_id=OuterRef("user_id"))
    ticket_match = Q(holder_email=OuterRef("email")) | Q(owner_id=OuterRef("user_id"))

    if segment.audience_kind == AudienceKind.CONFIRMED_BUYERS:
        orders = TicketOrder.objects.filter(event=event, status=TicketOrderStatus.CONFIRMED).filter(contact_match)
        if segment.ticket_type_id:
            orders = orders.filter(items__ticket_type_id=segment.ticket_type_id)
        return queryset.annotate(_crm_match=Exists(orders)).filter(_crm_match=True).distinct()

    if segment.audience_kind in {
        AudienceKind.TICKET_HOLDERS,
        AudienceKind.ATTENDEES,
        AudienceKind.NO_SHOWS,
    }:
        tickets = Ticket.objects.filter(event=event).filter(ticket_match)
        if segment.audience_kind == AudienceKind.TICKET_HOLDERS:
            tickets = tickets.filter(status__in=[TicketStatus.VALID, TicketStatus.USED])
        elif segment.audience_kind == AudienceKind.ATTENDEES:
            tickets = tickets.filter(status=TicketStatus.USED)
        else:
            if event.end_at > timezone.now():
                return queryset.none()
            tickets = tickets.filter(status=TicketStatus.VALID)
        if segment.ticket_type_id:
            tickets = tickets.filter(ticket_type_id=segment.ticket_type_id)
        return queryset.annotate(_crm_match=Exists(tickets)).filter(_crm_match=True).distinct()

    if segment.audience_kind == AudienceKind.WAITLIST:
        waitlist = TicketWaitlistEntry.objects.filter(
            ticket_type__event=event,
            status__in=[WaitlistStatus.WAITING, WaitlistStatus.OFFERED],
            user_id=OuterRef("user_id"),
        )
        if segment.ticket_type_id:
            waitlist = waitlist.filter(ticket_type_id=segment.ticket_type_id)
        return queryset.annotate(_crm_match=Exists(waitlist)).filter(_crm_match=True).distinct()

    if segment.audience_kind == AudienceKind.PARTNER_REFERRED:
        attributions = ReferralAttribution.objects.filter(
            campaign__event=event,
            status=AttributionStatus.CONFIRMED,
        ).filter(
            Q(order__customer_email=OuterRef("email")) | Q(order__buyer_id=OuterRef("user_id"))
        )
        if segment.ticket_type_id:
            attributions = attributions.filter(order__items__ticket_type_id=segment.ticket_type_id)
        return queryset.annotate(_crm_match=Exists(attributions)).filter(_crm_match=True).distinct()

    return queryset.none()


def campaign_metrics(campaign: CommunicationCampaign):
    recipients = campaign.recipients.all()
    audience_size = recipients.count()
    sent = recipients.filter(status=CampaignRecipientStatus.SENT).count()
    clicked_recipients = recipients.filter(click_count__gt=0).count()
    total_clicks = recipients.aggregate(total=Sum("click_count"))["total"] or 0
    confirmed = campaign.attributions.filter(status=CampaignAttributionStatus.CONFIRMED)
    conversions = confirmed.count()
    reversed_count = campaign.attributions.filter(status=CampaignAttributionStatus.REVERSED).count()
    revenue_by_currency = [
        {"currency": row["currency"] or "N/A", "amount": row["amount"] or 0, "orders": row["orders"]}
        for row in confirmed.values("currency").annotate(amount=Sum("revenue_amount"), orders=Count("id")).order_by("currency")
    ]
    return {
        "audience_size": audience_size,
        "queued": recipients.filter(status=CampaignRecipientStatus.QUEUED).count(),
        "processing": recipients.filter(status=CampaignRecipientStatus.PROCESSING).count(),
        "sent": sent,
        "failed": recipients.filter(status=CampaignRecipientStatus.FAILED).count(),
        "skipped": recipients.filter(status=CampaignRecipientStatus.SKIPPED).count(),
        "clicked_recipients": clicked_recipients,
        "total_clicks": total_clicks,
        "click_rate": round((clicked_recipients / sent) * 100, 1) if sent else 0,
        "conversions": conversions,
        "conversion_rate": round((conversions / clicked_recipients) * 100, 1) if clicked_recipients else 0,
        "reversed_conversions": reversed_count,
        "revenue_by_currency": revenue_by_currency,
    }
