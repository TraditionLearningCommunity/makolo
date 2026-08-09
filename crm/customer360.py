from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db.models import Max, Min, Q, Sum
from django.utils import timezone

from organizations.models import OrganizationFollow
from partners.models import AttributionStatus, ReferralAttribution
from payments.models import Payment, PaymentStatus
from promotions.models import PromotionRedemption, RedemptionStatus
from tickets.models import (
    Ticket,
    TicketOrder,
    TicketOrderStatus,
    TicketStatus,
    TicketTransfer,
    TicketWaitlistEntry,
    TransferStatus,
    WaitlistStatus,
)

from .models import (
    CampaignAttribution,
    CampaignAttributionStatus,
    CampaignRecipient,
    CampaignRecipientStatus,
    CRMContact,
)


BEHAVIOR_FILTER_KEY = "$behavior"
BEHAVIOR_FILTER_FIELDS = {
    "min_confirmed_orders",
    "max_days_since_last_order",
    "min_days_since_last_order",
    "min_attended_events",
    "min_promotion_redemptions",
    "min_partner_referred_orders",
    "min_spend_amount",
    "spend_currency",
}


def _identity_q(contact: CRMContact, *, email_field: str, user_field: str) -> Q:
    query = Q(**{f"{email_field}__iexact": contact.email})
    if contact.user_id:
        query |= Q(**{user_field: contact.user_id})
    return query


def contact_orders(contact: CRMContact):
    return TicketOrder.objects.filter(event__organization=contact.organization).filter(
        _identity_q(contact, email_field="customer_email", user_field="buyer_id")
    )


def contact_tickets(contact: CRMContact):
    return Ticket.objects.filter(event__organization=contact.organization).filter(
        _identity_q(contact, email_field="holder_email", user_field="owner_id")
    )


def contact_waitlist_entries(contact: CRMContact):
    if not contact.user_id:
        return TicketWaitlistEntry.objects.none()
    return TicketWaitlistEntry.objects.filter(
        ticket_type__event__organization=contact.organization,
        user_id=contact.user_id,
    )


def contact_transfers(contact: CRMContact):
    if not contact.user_id:
        return TicketTransfer.objects.none()
    return TicketTransfer.objects.filter(ticket__event__organization=contact.organization).filter(
        Q(sender_id=contact.user_id) | Q(recipient_id=contact.user_id)
    )


def segment_behavior_filters(segment) -> dict:
    payload = (segment.custom_filters or {}).get(BEHAVIOR_FILTER_KEY, {})
    return payload if isinstance(payload, dict) else {}


def validate_behavior_filters(raw) -> dict:
    if raw in (None, "", {}):
        return {}
    if not isinstance(raw, dict):
        raise ValueError("Les filtres comportementaux doivent former un objet clé/valeur.")

    unknown = set(raw) - BEHAVIOR_FILTER_FIELDS
    if unknown:
        raise ValueError(
            "Filtres comportementaux inconnus : " + ", ".join(sorted(unknown))
        )

    normalized = {}
    integer_fields = {
        "min_confirmed_orders",
        "max_days_since_last_order",
        "min_days_since_last_order",
        "min_attended_events",
        "min_promotion_redemptions",
        "min_partner_referred_orders",
    }
    for field in integer_fields:
        value = raw.get(field)
        if value in (None, ""):
            continue
        try:
            value = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field} doit être un entier positif.") from exc
        if value < 0:
            raise ValueError(f"{field} doit être positif ou nul.")
        normalized[field] = value

    min_days = normalized.get("min_days_since_last_order")
    max_days = normalized.get("max_days_since_last_order")
    if min_days is not None and max_days is not None and min_days > max_days:
        raise ValueError(
            "Le minimum de jours depuis la dernière commande ne peut pas dépasser le maximum."
        )

    amount = raw.get("min_spend_amount")
    currency = (raw.get("spend_currency") or "").strip().upper()
    if amount not in (None, ""):
        try:
            amount = Decimal(str(amount))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError("min_spend_amount doit être un montant valide.") from exc
        if amount < 0:
            raise ValueError("min_spend_amount doit être positif ou nul.")
        if len(currency) != 3:
            raise ValueError("Une devise ISO à trois lettres est requise avec min_spend_amount.")
        normalized["min_spend_amount"] = str(amount.quantize(Decimal("0.01")))
        normalized["spend_currency"] = currency
    elif currency:
        raise ValueError("spend_currency nécessite aussi min_spend_amount.")

    return normalized


def merge_behavior_filters(custom_filters, behavior_filters) -> dict:
    custom_filters = dict(custom_filters or {})
    custom_filters.pop(BEHAVIOR_FILTER_KEY, None)
    behavior = validate_behavior_filters(behavior_filters)
    if behavior:
        custom_filters[BEHAVIOR_FILTER_KEY] = behavior
    return custom_filters


def _recency_score(days_since_last_order):
    if days_since_last_order is None:
        return 0
    if days_since_last_order <= 30:
        return 5
    if days_since_last_order <= 90:
        return 4
    if days_since_last_order <= 180:
        return 3
    if days_since_last_order <= 365:
        return 2
    return 1


def _frequency_score(order_count):
    if order_count <= 0:
        return 0
    if order_count == 1:
        return 1
    if order_count == 2:
        return 2
    if order_count <= 4:
        return 3
    if order_count <= 9:
        return 4
    return 5


def _monetary_score(contact: CRMContact, currency: str, target_total: Decimal):
    if target_total <= 0:
        return 0
    cohort = defaultdict(lambda: Decimal("0.00"))
    rows = TicketOrder.objects.filter(
        event__organization=contact.organization,
        status=TicketOrderStatus.CONFIRMED,
        currency=currency,
    ).values("buyer_id", "customer_email", "total_amount")
    for row in rows.iterator():
        if row["buyer_id"]:
            key = ("user", str(row["buyer_id"]))
        else:
            key = ("email", (row["customer_email"] or "").lower())
        cohort[key] += row["total_amount"] or Decimal("0.00")
    totals = sorted(value for value in cohort.values() if value > 0)
    if not totals:
        return 1
    percentile = sum(1 for value in totals if value <= target_total) / len(totals)
    if percentile <= 0.20:
        return 1
    if percentile <= 0.40:
        return 2
    if percentile <= 0.60:
        return 3
    if percentile <= 0.80:
        return 4
    return 5


def _rfm_label(recency_score, frequency_score, monetary_score):
    if recency_score == 0 or frequency_score == 0:
        return "Nouveau / sans achat confirmé"
    if recency_score >= 4 and frequency_score >= 4 and monetary_score >= 4:
        return "Champion"
    if frequency_score >= 4 and recency_score >= 3:
        return "Fidèle"
    if recency_score == 5 and frequency_score <= 2:
        return "Nouveau client"
    if recency_score >= 4 and frequency_score <= 3:
        return "Prometteur"
    if recency_score <= 2 and frequency_score >= 3:
        return "À risque"
    if recency_score <= 2 and frequency_score <= 2:
        return "En sommeil"
    return "Actif"


def _relationship_label(recency_score, frequency_score, attended_events, clicked_campaigns):
    if recency_score >= 4 and frequency_score >= 3 and attended_events:
        return "Très engagé"
    if recency_score >= 4:
        return "Récent"
    if frequency_score >= 3 or attended_events >= 2 or clicked_campaigns >= 2:
        return "Engagé"
    if recency_score <= 2 and frequency_score:
        return "À réactiver"
    if frequency_score == 0:
        return "Prospect"
    return "Occasionnel"


def customer_360(contact: CRMContact, *, include_financials: bool = False) -> dict:
    now = timezone.now()
    orders = contact_orders(contact)
    confirmed_orders = orders.filter(status=TicketOrderStatus.CONFIRMED)
    tickets = contact_tickets(contact)
    waitlist = contact_waitlist_entries(contact)
    transfers = contact_transfers(contact)

    order_dates = confirmed_orders.aggregate(
        first=Min("confirmed_at"),
        last=Max("confirmed_at"),
    )
    last_order_at = order_dates["last"]
    days_since_last_order = (
        max((now - last_order_at).days, 0) if last_order_at else None
    )
    confirmed_count = confirmed_orders.count()
    attended_events = tickets.filter(status=TicketStatus.USED).values("event_id").distinct().count()
    no_show_events = tickets.filter(
        status=TicketStatus.VALID,
        event__end_at__lt=now,
    ).values("event_id").distinct().count()

    recipients = CampaignRecipient.objects.filter(
        campaign__organization=contact.organization,
        contact=contact,
    )
    clicked_campaigns = recipients.filter(click_count__gt=0).count()
    campaign_conversions = CampaignAttribution.objects.filter(
        campaign__organization=contact.organization,
        status=CampaignAttributionStatus.CONFIRMED,
    ).filter(Q(contact=contact) | Q(order__in=orders)).distinct().count()

    promotion_redemptions = PromotionRedemption.objects.filter(
        promotion__organization=contact.organization,
        order__in=orders,
        status=RedemptionStatus.CONFIRMED,
    ).count()
    partner_referred_orders = ReferralAttribution.objects.filter(
        campaign__organization=contact.organization,
        order__in=orders,
        status=AttributionStatus.CONFIRMED,
    ).count()

    recency = _recency_score(days_since_last_order)
    frequency = _frequency_score(confirmed_count)

    financial = None
    max_monetary_score = 0
    if include_financials:
        spend_rows = confirmed_orders.values("currency").annotate(amount=Sum("total_amount")).order_by("currency")
        spend_by_currency = []
        for row in spend_rows:
            amount = row["amount"] or Decimal("0.00")
            score = _monetary_score(contact, row["currency"], amount)
            max_monetary_score = max(max_monetary_score, score)
            spend_by_currency.append(
                {
                    "currency": row["currency"],
                    "amount": amount,
                    "monetary_score": score,
                }
            )
        refunded_by_currency = []
        refunds = Payment.objects.filter(
            order__in=orders,
            status=PaymentStatus.REFUNDED,
        ).values("currency").annotate(amount=Sum("amount")).order_by("currency")
        for row in refunds:
            refunded_by_currency.append(
                {"currency": row["currency"], "amount": row["amount"] or Decimal("0.00")}
            )
        financial = {
            "spend_by_currency": spend_by_currency,
            "refunded_by_currency": refunded_by_currency,
        }

    relationship_label = _relationship_label(
        recency,
        frequency,
        attended_events,
        clicked_campaigns,
    )
    rfm = {
        "recency_score": recency,
        "frequency_score": frequency,
        "days_since_last_order": days_since_last_order,
        "monetary_visible": include_financials,
        "monetary_by_currency": financial["spend_by_currency"] if financial else [],
        "label": _rfm_label(recency, frequency, max_monetary_score) if include_financials else None,
        "method": (
            "R: ancienneté du dernier achat; F: nombre de commandes confirmées; "
            "M: quintile de dépenses au sein de la même organisation et de la même devise."
        ),
    }

    follow = None
    if contact.user_id:
        follow = OrganizationFollow.objects.filter(
            organization=contact.organization,
            user_id=contact.user_id,
        ).first()

    return {
        "contact_id": contact.pk,
        "organization_id": contact.organization_id,
        "first_seen_at": contact.first_seen_at,
        "last_seen_at": contact.last_seen_at,
        "first_confirmed_order_at": order_dates["first"],
        "last_confirmed_order_at": last_order_at,
        "relationship_label": relationship_label,
        "orders": {
            "total": orders.count(),
            "confirmed": confirmed_count,
            "pending": orders.filter(status=TicketOrderStatus.PENDING).count(),
            "cancelled_or_expired": orders.filter(
                status__in=[TicketOrderStatus.CANCELLED, TicketOrderStatus.EXPIRED]
            ).count(),
            "distinct_events": confirmed_orders.values("event_id").distinct().count(),
        },
        "tickets": {
            "total": tickets.count(),
            "valid": tickets.filter(status=TicketStatus.VALID).count(),
            "used": tickets.filter(status=TicketStatus.USED).count(),
            "cancelled_or_refunded": tickets.filter(
                status__in=[TicketStatus.CANCELLED, TicketStatus.REFUNDED]
            ).count(),
            "attended_events": attended_events,
            "no_show_events": no_show_events,
        },
        "waitlist": {
            "total": waitlist.count(),
            "active": waitlist.filter(status__in=[WaitlistStatus.WAITING, WaitlistStatus.OFFERED]).count(),
            "converted": waitlist.filter(status=WaitlistStatus.CONVERTED).count(),
        },
        "transfers": {
            "total": transfers.count(),
            "accepted": transfers.filter(status=TransferStatus.ACCEPTED).count(),
            "sent": transfers.filter(sender_id=contact.user_id).count() if contact.user_id else 0,
            "received": transfers.filter(recipient_id=contact.user_id).count() if contact.user_id else 0,
        },
        "engagement": {
            "follows_organization": bool(follow),
            "campaigns_received": recipients.filter(status=CampaignRecipientStatus.SENT).count(),
            "campaigns_clicked": clicked_campaigns,
            "campaign_conversions": campaign_conversions,
            "promotion_redemptions": promotion_redemptions,
            "partner_referred_orders": partner_referred_orders,
        },
        "rfm": rfm,
        "financial": financial,
    }


def customer_timeline(
    contact: CRMContact,
    *,
    include_financials: bool = False,
    limit: int = 100,
) -> list[dict]:
    events = []
    orders = contact_orders(contact).select_related("event")
    tickets = contact_tickets(contact).select_related("event", "ticket_type")

    def add(at, kind, title, detail="", **metadata):
        if not at:
            return
        events.append(
            {
                "at": at,
                "kind": kind,
                "title": title,
                "detail": detail,
                "metadata": metadata,
            }
        )

    if contact.user_id:
        follow = OrganizationFollow.objects.filter(
            organization=contact.organization,
            user_id=contact.user_id,
        ).first()
        if follow:
            add(
                follow.followed_at,
                "follow",
                "A commencé à suivre l’organisateur",
                contact.organization.name,
            )

    for order in orders[:250]:
        metadata = {"event": order.event.title, "status": order.status}
        if include_financials:
            metadata.update({"amount": order.total_amount, "currency": order.currency, "reference": order.reference})
        add(
            order.created_at,
            "order",
            "Commande créée",
            order.event.title,
            **metadata,
        )
        if order.confirmed_at:
            add(
                order.confirmed_at,
                "order_confirmed",
                "Commande confirmée",
                order.event.title,
                **metadata,
            )

    if include_financials:
        payments = Payment.objects.filter(
            order__in=orders,
            status__in=[PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED],
        ).select_related("order__event")
        for payment in payments[:250]:
            add(
                payment.succeeded_at or payment.processed_at or payment.created_at,
                "payment",
                "Paiement réussi" if payment.status == PaymentStatus.SUCCEEDED else "Paiement remboursé",
                payment.order.event.title,
                amount=payment.amount,
                currency=payment.currency,
                provider=payment.provider,
                method=payment.method,
            )

    for ticket in tickets.filter(used_at__isnull=False)[:250]:
        add(
            ticket.used_at,
            "checkin",
            "Présence enregistrée",
            ticket.event.title,
            event=ticket.event.title,
            ticket_type=ticket.ticket_type.name,
        )

    waitlist = contact_waitlist_entries(contact).select_related("ticket_type__event")
    for entry in waitlist[:250]:
        add(
            entry.created_at,
            "waitlist",
            "Entrée en liste d’attente",
            entry.ticket_type.event.title,
            event=entry.ticket_type.event.title,
            ticket_type=entry.ticket_type.name,
            status=entry.status,
        )
        if entry.offered_at:
            add(
                entry.offered_at,
                "waitlist_offer",
                "Offre de liste d’attente",
                entry.ticket_type.event.title,
                event=entry.ticket_type.event.title,
                ticket_type=entry.ticket_type.name,
            )
        if entry.converted_at:
            add(
                entry.converted_at,
                "waitlist_converted",
                "Liste d’attente convertie en commande",
                entry.ticket_type.event.title,
                event=entry.ticket_type.event.title,
                ticket_type=entry.ticket_type.name,
            )

    transfers = contact_transfers(contact).select_related("ticket__event", "sender", "recipient")
    for transfer in transfers[:250]:
        direction = "envoyé" if transfer.sender_id == contact.user_id else "reçu"
        add(
            transfer.created_at,
            "transfer",
            f"Transfert de billet {direction}",
            transfer.ticket.event.title,
            event=transfer.ticket.event.title,
            direction=direction,
            status=transfer.status,
        )
        if transfer.accepted_at:
            add(
                transfer.accepted_at,
                "transfer_accepted",
                "Transfert de billet accepté",
                transfer.ticket.event.title,
                event=transfer.ticket.event.title,
                direction=direction,
            )

    recipients = CampaignRecipient.objects.filter(
        campaign__organization=contact.organization,
        contact=contact,
    ).select_related("campaign")
    for recipient in recipients[:250]:
        if recipient.sent_at:
            add(
                recipient.sent_at,
                "campaign",
                "Campagne reçue",
                recipient.campaign.name,
                campaign=recipient.campaign.name,
            )
        if recipient.first_clicked_at:
            add(
                recipient.first_clicked_at,
                "campaign_click",
                "Campagne cliquée",
                recipient.campaign.name,
                campaign=recipient.campaign.name,
                click_count=recipient.click_count,
            )

    campaign_attributions = CampaignAttribution.objects.filter(
        campaign__organization=contact.organization,
        status=CampaignAttributionStatus.CONFIRMED,
    ).filter(Q(contact=contact) | Q(order__in=orders)).select_related("campaign", "order__event")
    for attribution in campaign_attributions[:250]:
        metadata = {"campaign": attribution.campaign.name, "event": attribution.order.event.title}
        if include_financials:
            metadata.update({"amount": attribution.revenue_amount, "currency": attribution.currency})
        add(
            attribution.confirmed_at or attribution.captured_at,
            "campaign_conversion",
            "Conversion attribuée à une campagne CRM",
            attribution.campaign.name,
            **metadata,
        )

    promotions = PromotionRedemption.objects.filter(
        promotion__organization=contact.organization,
        order__in=orders,
        status=RedemptionStatus.CONFIRMED,
    ).select_related("promotion", "code", "order__event")
    for redemption in promotions[:250]:
        metadata = {
            "promotion": redemption.promotion.name,
            "code": redemption.code.code,
            "event": redemption.order.event.title,
        }
        if include_financials:
            metadata.update(
                {
                    "discount_amount": redemption.discount_amount,
                    "final_amount": redemption.final_amount,
                    "currency": redemption.currency,
                }
            )
        add(
            redemption.confirmed_at or redemption.reserved_at,
            "promotion",
            "Code promotionnel converti",
            redemption.promotion.name,
            **metadata,
        )

    referrals = ReferralAttribution.objects.filter(
        campaign__organization=contact.organization,
        order__in=orders,
        status=AttributionStatus.CONFIRMED,
    ).select_related("partner", "campaign", "order__event")
    for attribution in referrals[:250]:
        add(
            attribution.confirmed_at or attribution.attributed_at,
            "partner",
            "Acquisition attribuée à un partenaire",
            attribution.partner.display_name,
            partner=attribution.partner.display_name,
            event=attribution.order.event.title,
        )

    events.sort(key=lambda item: item["at"], reverse=True)
    return events[: max(1, min(int(limit or 100), 500))]
