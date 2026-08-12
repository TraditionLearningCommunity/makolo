from datetime import timedelta
from decimal import Decimal

from django.db.models import (
    Count,
    DateTimeField,
    DecimalField,
    Exists,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
)
from django.db.models.functions import Coalesce
from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission
from organizations.models import OrganizationFollow
from partners.models import AttributionStatus, ReferralAttribution
from promotions.models import PromotionRedemption, RedemptionStatus
from tickets.models import (
    Ticket,
    TicketOrder,
    TicketOrderStatus,
    TicketStatus,
    TicketWaitlistEntry,
    WaitlistStatus,
)

from .customer360 import BEHAVIOR_FILTER_KEY, segment_behavior_filters
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


def _visible_organization_ids(user):
    if not getattr(user, "is_authenticated", False):
        return []
    return space_ids_with_permission(user, PermissionCode.CRM_VIEW)


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


def _apply_behavior_filters(queryset, segment: AudienceSegment):
    behavior = segment_behavior_filters(segment)
    if not behavior:
        return queryset

    order_match = Q(customer_email__iexact=OuterRef("email")) | Q(buyer_id=OuterRef("user_id"))
    confirmed_orders = TicketOrder.objects.filter(
        event__organization=segment.organization,
        status=TicketOrderStatus.CONFIRMED,
    ).filter(order_match)

    if "min_confirmed_orders" in behavior:
        count_subquery = (
            confirmed_orders.order_by()
            .values("event__organization_id")
            .annotate(total=Count("id"))
            .values("total")[:1]
        )
        queryset = queryset.annotate(
            _behavior_order_count=Coalesce(
                Subquery(count_subquery, output_field=IntegerField()),
                Value(0),
            )
        ).filter(_behavior_order_count__gte=behavior["min_confirmed_orders"])

    if "max_days_since_last_order" in behavior or "min_days_since_last_order" in behavior:
        last_order_subquery = confirmed_orders.order_by("-confirmed_at").values("confirmed_at")[:1]
        queryset = queryset.annotate(
            _behavior_last_order=Subquery(last_order_subquery, output_field=DateTimeField())
        )
        if "max_days_since_last_order" in behavior:
            threshold = timezone.now() - timedelta(days=behavior["max_days_since_last_order"])
            queryset = queryset.filter(_behavior_last_order__gte=threshold)
        if "min_days_since_last_order" in behavior:
            threshold = timezone.now() - timedelta(days=behavior["min_days_since_last_order"])
            queryset = queryset.filter(_behavior_last_order__lte=threshold)

    if "min_attended_events" in behavior:
        ticket_match = Q(holder_email__iexact=OuterRef("email")) | Q(owner_id=OuterRef("user_id"))
        attended_subquery = (
            Ticket.objects.filter(
                event__organization=segment.organization,
                status=TicketStatus.USED,
            )
            .filter(ticket_match)
            .order_by()
            .values("event__organization_id")
            .annotate(total=Count("event_id", distinct=True))
            .values("total")[:1]
        )
        queryset = queryset.annotate(
            _behavior_attended_count=Coalesce(
                Subquery(attended_subquery, output_field=IntegerField()),
                Value(0),
            )
        ).filter(_behavior_attended_count__gte=behavior["min_attended_events"])

    if "min_promotion_redemptions" in behavior:
        promo_subquery = (
            PromotionRedemption.objects.filter(
                promotion__organization=segment.organization,
                status=RedemptionStatus.CONFIRMED,
            )
            .filter(
                Q(order__customer_email__iexact=OuterRef("email"))
                | Q(order__buyer_id=OuterRef("user_id"))
            )
            .order_by()
            .values("promotion__organization_id")
            .annotate(total=Count("id"))
            .values("total")[:1]
        )
        queryset = queryset.annotate(
            _behavior_promo_count=Coalesce(
                Subquery(promo_subquery, output_field=IntegerField()),
                Value(0),
            )
        ).filter(_behavior_promo_count__gte=behavior["min_promotion_redemptions"])

    if "min_partner_referred_orders" in behavior:
        referral_subquery = (
            ReferralAttribution.objects.filter(
                campaign__organization=segment.organization,
                status=AttributionStatus.CONFIRMED,
            )
            .filter(
                Q(order__customer_email__iexact=OuterRef("email"))
                | Q(order__buyer_id=OuterRef("user_id"))
            )
            .order_by()
            .values("campaign__organization_id")
            .annotate(total=Count("id"))
            .values("total")[:1]
        )
        queryset = queryset.annotate(
            _behavior_partner_count=Coalesce(
                Subquery(referral_subquery, output_field=IntegerField()),
                Value(0),
            )
        ).filter(_behavior_partner_count__gte=behavior["min_partner_referred_orders"])

    if "min_spend_amount" in behavior:
        spend_subquery = (
            confirmed_orders.filter(currency=behavior["spend_currency"])
            .order_by()
            .values("event__organization_id")
            .annotate(total=Sum("total_amount"))
            .values("total")[:1]
        )
        queryset = queryset.annotate(
            _behavior_spend=Coalesce(
                Subquery(
                    spend_subquery,
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                ),
                Value(
                    Decimal("0.00"),
                    output_field=DecimalField(max_digits=14, decimal_places=2),
                ),
            )
        ).filter(_behavior_spend__gte=Decimal(behavior["min_spend_amount"]))

    return queryset


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
        if field_key == BEHAVIOR_FILTER_KEY:
            continue
        values = CRMContactFieldValue.objects.filter(
            contact_id=OuterRef("pk"),
            field__organization=segment.organization,
            field__key=field_key,
            field__is_active=True,
            value=expected_value,
        )
        queryset = queryset.annotate(
            **{f"_crm_field_{str(field_key).replace('-', '_')}": Exists(values)}
        ).filter(**{f"_crm_field_{str(field_key).replace('-', '_')}": True})

    return _apply_behavior_filters(queryset, segment)


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
    if segment.audience_kind == AudienceKind.CONFIRMED_BUYERS:
        orders = TicketOrder.objects.filter(
            event=event,
            status=TicketOrderStatus.CONFIRMED,
        ).filter(contact_match)
        return queryset.annotate(_crm_match=Exists(orders)).filter(_crm_match=True).distinct()

    if segment.audience_kind == AudienceKind.WAITLIST:
        waitlist = TicketWaitlistEntry.objects.filter(
            ticket_type__event=event,
            status__in=[WaitlistStatus.WAITING, WaitlistStatus.OFFERED],
        ).filter(Q(user_id=OuterRef("user_id")))
        return queryset.annotate(_crm_match=Exists(waitlist)).filter(_crm_match=True).distinct()

    ticket_filters = Q(event=event)
    if segment.ticket_type_id:
        ticket_filters &= Q(ticket_type=segment.ticket_type)
    tickets = Ticket.objects.filter(ticket_filters).filter(
        Q(holder_email=OuterRef("email")) | Q(owner_id=OuterRef("user_id"))
    )
    if segment.audience_kind == AudienceKind.ATTENDEES:
        tickets = tickets.filter(status=TicketStatus.USED)
    elif segment.audience_kind == AudienceKind.NO_SHOWS:
        tickets = tickets.exclude(status=TicketStatus.USED)
    elif segment.audience_kind == AudienceKind.PARTNER_REFERRED:
        referrals = ReferralAttribution.objects.filter(
            campaign__organization=segment.organization,
            event=event,
            status=AttributionStatus.CONFIRMED,
        ).filter(
            Q(order__customer_email=OuterRef("email"))
            | Q(order__buyer_id=OuterRef("user_id"))
        )
        return queryset.annotate(_crm_match=Exists(referrals)).filter(_crm_match=True).distinct()

    return queryset.annotate(_crm_match=Exists(tickets)).filter(_crm_match=True).distinct()


def campaign_delivery_summary(campaign: CommunicationCampaign):
    grouped = campaign.recipients.values("status").annotate(total=Count("id"))
    summary = {choice: 0 for choice, _label in CampaignRecipientStatus.choices}
    for item in grouped:
        summary[item["status"]] = item["total"]
    return summary


def campaign_conversion_summary(campaign: CommunicationCampaign):
    grouped = campaign.attributions.values("status", "currency").annotate(
        orders=Count("id"),
        revenue=Sum("revenue_amount"),
    )
    return [
        {
            "status": item["status"],
            "currency": item["currency"],
            "orders": item["orders"],
            "revenue": item["revenue"] or Decimal("0.00"),
        }
        for item in grouped
    ]


def attributed_revenue_by_currency(campaign: CommunicationCampaign):
    grouped = (
        campaign.attributions.filter(status=CampaignAttributionStatus.CONFIRMED)
        .values("currency")
        .annotate(revenue=Sum("revenue_amount"), orders=Count("id"))
        .order_by("currency")
    )
    return [
        {
            "currency": item["currency"],
            "revenue": item["revenue"] or Decimal("0.00"),
            "orders": item["orders"],
        }
        for item in grouped
    ]
