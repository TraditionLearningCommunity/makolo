from __future__ import annotations

from datetime import timedelta

from discovery.models import EventBookmark
from events.models import EventStatus
from growth.models import (
    EventFeedback,
    MarketingAttribution,
    MarketingAttributionStatus,
    MarketingChannel,
    MarketingLink,
    MarketingLinkVisit,
)
from notifications.models import (
    DeliveryChannel,
    DeliveryStatus,
    Notification,
    NotificationCategory,
    NotificationDelivery,
    NotificationKind,
)
from tickets.models import TicketOrderStatus

from .common import SeedContext, backdate, choose, stable_token, upsert


def _seed_notifications(ctx: SeedContext) -> None:
    kinds = [
        (NotificationKind.TICKETS_ISSUED, NotificationCategory.TICKET, "Billet disponible"),
        (NotificationKind.PAYMENT_SUCCEEDED, NotificationCategory.PAYMENT, "Paiement confirmé"),
        (NotificationKind.EVENT_REMINDER, NotificationCategory.EVENT, "Votre événement approche"),
        (NotificationKind.SYSTEM, NotificationCategory.SYSTEM, "Nouveautés Makolo"),
    ]
    for i, user in enumerate(ctx.users[:min(100, len(ctx.users))]):
        for j in range(2 if i >= 40 else 3):
            kind, category, title = kinds[(i+j) % len(kinds)]
            created = ctx.as_of - timedelta(days=(i * 7 + j * 19) % 420, hours=j)
            notification = upsert(Notification, f"user-{i}-notification-{j}", defaults={
                "recipient": user,
                "kind": kind,
                "category": category,
                "title": title,
                "message": choose([
                    "Votre activité Makolo a bien été prise en compte.",
                    "Retrouvez les informations et actions utiles directement dans votre espace.",
                    "Merci de faire partie de la communauté Makolo.",
                ], i+j),
                "action_url": "/me/accesses/" if category == NotificationCategory.TICKET else "/",
                "dedup_key": f"demo-notif-{i}-{j}",
                "metadata": {"seed": "makolo-demo", "target": category},
                "read_at": created + timedelta(hours=4) if (i+j) % 3 else None,
            })
            backdate(notification, created_at=created, updated_at=min(ctx.as_of, created + timedelta(hours=4)))
            channel = DeliveryChannel.EMAIL if j % 2 == 0 else DeliveryChannel.PUSH
            status = choose([DeliveryStatus.SENT, DeliveryStatus.SENT, DeliveryStatus.SKIPPED, DeliveryStatus.FAILED, DeliveryStatus.QUEUED], i+j)
            delivery = upsert(NotificationDelivery, f"notification-{i}-{j}-delivery", defaults={
                "notification": notification,
                "channel": channel,
                "destination": user.email if channel == DeliveryChannel.EMAIL else f"device:{user.id}",
                "status": status,
                "scheduled_for": created,
                "attempts": 1 if status in {DeliveryStatus.SENT, DeliveryStatus.FAILED} else 0,
                "max_attempts": 3,
                "provider_reference": f"DEMO-DEL-{i:03d}-{j}" if status == DeliveryStatus.SENT else "",
                "last_error": "Erreur provider simulée." if status == DeliveryStatus.FAILED else "",
                "skipped_reason": "Préférence utilisateur." if status == DeliveryStatus.SKIPPED else "",
                "sent_at": created + timedelta(minutes=2) if status == DeliveryStatus.SENT else None,
            })
            backdate(delivery, created_at=created, updated_at=min(ctx.as_of, created + timedelta(minutes=3)))


def _seed_discovery_and_growth(ctx: SeedContext) -> None:
    public_future = [e for e in ctx.events if e.status == EventStatus.PUBLISHED and e.start_at > ctx.as_of and e.visibility == "public"]
    for i, user in enumerate(ctx.users[:min(120, len(ctx.users))]):
        for j, event in enumerate(public_future[:3]):
            if (i+j) % 2:
                bookmark = upsert(EventBookmark, f"user-{i}-bookmark-{event.id}", defaults={"user": user, "event": event})
                backdate(bookmark, created_at=ctx.as_of - timedelta(days=(i+j) % 70))

    attribution_orders_used = set()
    channels = list(MarketingChannel.values)
    for i, event in enumerate([e for e in ctx.events if e.organization_id and e.status in {EventStatus.PUBLISHED, EventStatus.COMPLETED}][:18]):
        owner = event.organization.memberships.filter(role="owner", is_active=True).first().user
        campaign = next((c for c in ctx.crm_campaigns if c.organization_id == event.organization_id and (not c.event_id or c.event_id == event.id)), None)
        link = upsert(MarketingLink, f"event-{event.id}-marketing-link", defaults={
            "organization": event.organization,
            "event": event,
            "crm_campaign": campaign,
            "name": f"{choose(['WhatsApp communauté', 'Instagram Story', 'Affiche QR', 'Email newsletter'], i)} — {event.title[:60]}",
            "channel": channels[i % len(channels)],
            "code": f"DM{i+1:05d}",
            "attribution_window_days": 30,
            "is_active": event.start_at > ctx.as_of,
            "created_by": owner,
        })
        backdate(link, created_at=event.start_at - timedelta(days=75), updated_at=min(ctx.as_of, event.start_at - timedelta(days=10)))
        visits = []
        for j in range(8):
            user = ctx.users[(i * 9 + j + 22) % len(ctx.users)] if j % 3 != 0 else None
            visit = upsert(MarketingLinkVisit, f"link-{i}-visit-{j}", defaults={
                "link": link,
                "user": user,
                "session_key_hash": stable_token(f"marketing-session-{i}-{j}", 64),
                "referrer_domain": choose(["wa.me", "instagram.com", "facebook.com", "", "mail.google.com"], i+j),
                "visited_at": min(ctx.as_of, event.start_at - timedelta(days=max(1, 45-j*3))),
            })
            visits.append(visit)
        order = next((
            o for o in ctx.orders
            if o.event_id == event.id and o.status == TicketOrderStatus.CONFIRMED and o.id not in attribution_orders_used
        ), None)
        if order:
            attribution_orders_used.add(order.id)
            upsert(MarketingAttribution, f"growth-attribution-{i}", defaults={
                "order": order,
                "link": link,
                "visit": visits[1],
                "status": MarketingAttributionStatus.CONFIRMED,
                "revenue_amount": order.total_amount,
                "currency": order.currency,
                "attributed_at": order.created_at,
                "confirmed_at": order.confirmed_at,
                "reversed_at": None,
            })

    past_events = [e for e in ctx.events if e.end_at < ctx.as_of and e.status == EventStatus.COMPLETED][:12]
    for i, event in enumerate(past_events):
        event_tickets = [t for t in ctx.tickets if t.event_id == event.id and t.owner_id][:10]
        seen_users = set()
        for j, ticket in enumerate(event_tickets):
            if ticket.owner_id in seen_users:
                continue
            seen_users.add(ticket.owner_id)
            feedback = upsert(EventFeedback, f"feedback-{event.id}-{ticket.owner_id}", defaults={
                "event": event,
                "user": ticket.owner,
                "rating": 3 + ((i+j) % 3),
                "comment": choose([
                    "Bonne organisation, accès rapide et équipe accueillante.",
                    "Très bonne ambiance. J'aimerais plus d'informations avant l'événement.",
                    "Billetterie simple et scan rapide à l'entrée.",
                    "Expérience positive, je reviendrai à une prochaine édition.",
                ], i+j),
            })
            backdate(feedback, created_at=min(ctx.as_of, event.end_at + timedelta(days=1+j%3)), updated_at=min(ctx.as_of, event.end_at + timedelta(days=2+j%3)))
