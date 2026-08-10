from __future__ import annotations

import hashlib
from collections import defaultdict
from datetime import timedelta

from events.models import (
    Event,
    EventCategory,
    EventStatus,
    EventVenue,
    EventVisibility,
    VenueKind,
)
from payments.models import (
    Payment,
    PaymentEvent,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
    Refund,
    RefundStatus,
)
from scanner.models import EventAccessGate, ScanLog, ScanResult, ScannerAssignment
from tickets.models import (
    Ticket,
    TicketOrder,
    TicketOrderItem,
    TicketOrderStatus,
    TicketStatus,
    TicketTransfer,
    TicketType,
    TicketWaitlistEntry,
    TransferStatus,
    WaitlistStatus,
)

from .common import SeedContext, backdate, choose, dt, money, stable_token, stable_uuid, upsert


CATEGORY_SPECS = [
    ("musique", "Musique & Concerts"),
    ("business", "Business & Networking"),
    ("tech", "Technologie & Innovation"),
    ("culture", "Culture & Arts"),
    ("sport", "Sport & Bien-être"),
    ("formation", "Formation & Carrière"),
    ("gastronomie", "Gastronomie"),
    ("communaute", "Communauté & Impact"),
]

VENUE_SPECS = [
    ("Pullman Grand Karavia — Démo", "Lubumbashi", "CD", -11.6532, 27.4781),
    ("Salle Hypnose — Démo", "Lubumbashi", "CD", -11.6701, 27.4821),
    ("Centre Arrupe — Démo", "Lubumbashi", "CD", -11.6748, 27.4750),
    ("Palais du Peuple — Démo", "Kinshasa", "CD", -4.3317, 15.3032),
    ("Silikin Village — Démo", "Kinshasa", "CD", -4.3199, 15.2890),
    ("Kolwezi Conference Hub — Démo", "Kolwezi", "CD", -10.7165, 25.4662),
    ("Likasi Civic Hall — Démo", "Likasi", "CD", -10.9830, 26.7350),
    ("Goma Creative Hall — Démo", "Goma", "CD", -1.6810, 29.2220),
    ("Kisangani Riverside — Démo", "Kisangani", "CD", 0.5159, 25.1904),
]

EVENT_BLUEPRINTS = [
    ("Lushi Summer Vibes 2024", 2024, 3, 16, "musique", "Lubumbashi"),
    ("Katanga Entrepreneurs Breakfast #1", 2024, 4, 27, "business", "Lubumbashi"),
    ("Women in Tech Congo 2024", 2024, 5, 18, "tech", "Kinshasa"),
    ("Festival Saveurs du Katanga 2024", 2024, 7, 6, "gastronomie", "Lubumbashi"),
    ("Makolo Community Day 2024", 2024, 8, 24, "communaute", "Lubumbashi"),
    ("Copperbelt Fitness Challenge 2024", 2024, 10, 12, "sport", "Kolwezi"),
    ("Creative Goma Sessions 2024", 2024, 11, 9, "culture", "Goma"),
    ("Leadership Jeunesse RDC 2024", 2024, 12, 7, "formation", "Kinshasa"),
    ("New Year Business Mixer 2025", 2025, 1, 25, "business", "Lubumbashi"),
    ("Code & Coffee Kinshasa 2025", 2025, 2, 22, "tech", "Kinshasa"),
    ("Lushi Acoustic Night 2025", 2025, 3, 29, "musique", "Lubumbashi"),
    ("Kolwezi Mining Innovation Forum", 2025, 5, 17, "business", "Kolwezi"),
    ("Culture Urbaine Congo 2025", 2025, 6, 21, "culture", "Kinshasa"),
    ("Makolo Sports Weekend 2025", 2025, 8, 2, "sport", "Lubumbashi"),
    ("Food Market Lushi 2025", 2025, 9, 20, "gastronomie", "Lubumbashi"),
    ("Digital Careers Bootcamp 2025", 2025, 11, 15, "formation", "Lubumbashi"),
    ("Goma Creators Meetup 2026", 2026, 1, 31, "culture", "Goma"),
    ("Kinshasa Startup Exchange 2026", 2026, 3, 14, "business", "Kinshasa"),
    ("Lushi Gospel & Culture Night 2026", 2026, 4, 25, "musique", "Lubumbashi"),
    ("Women Lead Katanga 2026", 2026, 6, 13, "formation", "Lubumbashi"),
    ("Makolo Community Run 2026", 2026, 7, 18, "sport", "Lubumbashi"),
    ("Tech Builders Lubumbashi", 2026, 8, 29, "tech", "Lubumbashi"),
    ("Rentrée Business & Networking", 2026, 9, 19, "business", "Lubumbashi"),
    ("Kinshasa Creator Economy Forum", 2026, 10, 10, "culture", "Kinshasa"),
    ("Katanga Food Festival 2026", 2026, 10, 31, "gastronomie", "Lubumbashi"),
    ("Africa Product Meetup RDC", 2026, 11, 21, "tech", "Kinshasa"),
    ("Makolo End of Year Live 2026", 2026, 12, 19, "musique", "Lubumbashi"),
    ("Leadership & Impact Summit 2027", 2027, 1, 30, "formation", "Kinshasa"),
    ("Lushi Tech Conference 2027", 2027, 3, 20, "tech", "Lubumbashi"),
    ("Copperbelt Business Expo 2027", 2027, 5, 15, "business", "Kolwezi"),
    ("Goma Arts Week 2027", 2027, 6, 26, "culture", "Goma"),
    ("Makolo Summer Festival 2027", 2027, 8, 7, "musique", "Lubumbashi"),
    ("Congo Community Games 2027", 2027, 9, 18, "sport", "Kinshasa"),
    ("Taste of Congo 2027", 2027, 10, 23, "gastronomie", "Lubumbashi"),
    ("Future of Work RDC 2027", 2027, 11, 20, "formation", "Kinshasa"),
    ("Makolo Year End Experience 2027", 2027, 12, 18, "musique", "Lubumbashi"),
]


def _event_org_index(category_slug: str, city: str, i: int) -> int:
    if category_slug == "business":
        return 1
    if category_slug == "tech":
        return 2
    if category_slug == "sport":
        return 3
    if city == "Goma":
        return 4
    if category_slug == "formation":
        return 5
    if category_slug == "gastronomie":
        return 6
    return 0


def seed_events_and_commerce(ctx: SeedContext) -> None:
    categories = {}
    for slug, name in CATEGORY_SPECS:
        categories[slug] = upsert(EventCategory, slug, defaults={
            "name": name,
            "slug": slug,
            "description": f"Événements de démonstration Makolo : {name}.",
            "is_active": True,
        })

    venues = []
    for i, (name, city, country, lat, lon) in enumerate(VENUE_SPECS):
        venue = upsert(EventVenue, f"venue-{i}", defaults={
            "name": name,
            "kind": VenueKind.PHYSICAL,
            "address": f"{20+i}, Avenue de la République",
            "city": city,
            "country": country,
            "latitude": lat,
            "longitude": lon,
            "online_url": "",
            "is_active": True,
        })
        venues.append(venue)
    online = upsert(EventVenue, "online", defaults={
        "name": "Makolo Live Room — Démo",
        "kind": VenueKind.ONLINE,
        "address": "",
        "city": "",
        "country": "CD",
        "latitude": None,
        "longitude": None,
        "online_url": "https://example.com/makolo-live-room",
        "is_active": True,
    })
    venues.append(online)

    ctx.events.clear()
    for i, (title, year, month, day, category_slug, city) in enumerate(EVENT_BLUEPRINTS):
        start = dt(year, month, day, 16 if category_slug in {"musique", "culture"} else 10)
        end = start + timedelta(hours=5 if category_slug in {"musique", "culture"} else 7)
        org_index = _event_org_index(category_slug, city, i) % len(ctx.organizations)
        org = ctx.organizations[org_index]
        organizer = org.memberships.filter(role="owner", is_active=True).first().user
        venue = next((v for v in venues if v.city == city), venues[0])

        if start < ctx.as_of:
            status = EventStatus.COMPLETED
            visibility = EventVisibility.PUBLIC
        else:
            status = EventStatus.PUBLISHED
            visibility = EventVisibility.PUBLIC

        if i == 5:
            status = EventStatus.CANCELLED
        elif i == 24:
            visibility = EventVisibility.UNLISTED
        elif i == 30:
            status = EventStatus.DRAFT
            visibility = EventVisibility.PRIVATE
        elif i == 34:
            visibility = EventVisibility.PRIVATE
        if org.verification_status == "suspended":
            status = EventStatus.DRAFT
            visibility = EventVisibility.PRIVATE

        registration_start = start - timedelta(days=90)
        registration_end = start - timedelta(hours=1)
        published_at = start - timedelta(days=100) if status in {EventStatus.PUBLISHED, EventStatus.COMPLETED} else None
        event = upsert(Event, f"event-{i:03d}", defaults={
            "organizer": organizer,
            "organization": org,
            "category": categories[category_slug],
            "venue": venue,
            "title": title,
            "slug": f"demo-{year}-{i+1:02d}-{stable_token(title, 6)}",
            "short_description": f"{title} : une expérience Makolo pensée pour la communauté de {city}.",
            "description": (
                f"{title} réunit participants, intervenants et partenaires autour d'une expérience "
                f"réaliste de démonstration. Billetterie, communication, accès et suivi sont gérés dans Makolo."
            ),
            "status": status,
            "visibility": visibility,
            "start_at": start,
            "end_at": end,
            "registration_start_at": registration_start,
            "registration_end_at": registration_end,
            "timezone": "Africa/Kinshasa" if city == "Kinshasa" else "Africa/Lubumbashi",
            "capacity": choose([120, 180, 250, 400, 600, 1000], i),
            "published_at": published_at,
            "cancelled_at": start - timedelta(days=20) if status == EventStatus.CANCELLED else None,
            "metadata": {
                "seed": "makolo-demo",
                "edition": year,
                "audience": choose(["grand_public", "professionals", "community", "students"], i),
                "featured": i % 7 == 0,
            },
        })
        created = start - timedelta(days=130)
        backdate(event, created_at=created, updated_at=min(ctx.as_of, created + timedelta(days=45)))
        ctx.events.append(event)

    ticket_types_by_event = {}
    ctx.ticket_types.clear()
    for i, event in enumerate(ctx.events):
        currency = "CDF" if i % 5 == 1 else "USD"
        if currency == "USD":
            prices = [money(0 if i % 9 == 0 else 10 + (i % 4) * 5), money(25 + (i % 4) * 5), money(50 + (i % 5) * 10)]
        else:
            prices = [money(0 if i % 9 == 0 else 20000 + (i % 4) * 5000), money(50000 + (i % 3) * 10000), money(100000 + (i % 4) * 25000)]
        names = ["Standard", "Premium", "VIP"]
        types = []
        for j, (name, price) in enumerate(zip(names, prices)):
            qty = max(20, (event.capacity or 300) // (2 + j))
            ticket_type = upsert(TicketType, f"event-{i}-type-{j}", defaults={
                "event": event,
                "name": name,
                "slug": name.lower(),
                "description": f"Accès {name.lower()} pour {event.title}.",
                "price": price,
                "currency": currency,
                "quantity_total": qty,
                "reserved_quantity": 0,
                "issued_quantity": 0,
                "sales_start_at": event.registration_start_at,
                "sales_end_at": event.registration_end_at,
                "min_per_order": 1,
                "max_per_order": 6 if j == 0 else 4,
                "is_active": True,
                "is_public": j != 2 or i % 6 != 0,
            })
            backdate(ticket_type, created_at=event.created_at + timedelta(days=5+j), updated_at=min(ctx.as_of, event.created_at + timedelta(days=30)))
            types.append(ticket_type)
            ctx.ticket_types.append(ticket_type)
        ticket_types_by_event[event.pk] = types

    issued_counts = defaultdict(int)
    reserved_counts = defaultdict(int)
    ctx.orders.clear()
    ctx.tickets.clear()
    ctx.payments.clear()

    eligible_events = [
        event for event in ctx.events
        if event.status in {EventStatus.PUBLISHED, EventStatus.COMPLETED}
        and event.visibility != EventVisibility.PRIVATE
    ]
    order_seq = 0
    for event_index, event in enumerate(eligible_events):
        type_options = ticket_types_by_event[event.pk]
        for n in range(ctx.cfg["orders_per_event"]):
            order_seq += 1
            buyer = ctx.users[(event_index * 11 + n * 3 + 14) % len(ctx.users)]
            ticket_type = type_options[n % len(type_options)]
            quantity = 1 + (1 if n % 5 == 0 else 0)
            unit_price = ticket_type.price
            total = unit_price * quantity
            created = event.start_at - timedelta(days=max(2, 75 - n * 3 - (event_index % 8)))
            if created > ctx.as_of:
                created = ctx.as_of - timedelta(days=(n % 12) + 1)

            if event.start_at < ctx.as_of:
                status = choose(
                    [TicketOrderStatus.CONFIRMED, TicketOrderStatus.CONFIRMED, TicketOrderStatus.CONFIRMED,
                     TicketOrderStatus.CONFIRMED, TicketOrderStatus.CANCELLED, TicketOrderStatus.EXPIRED],
                    n + event_index,
                )
            else:
                status = choose(
                    [TicketOrderStatus.CONFIRMED, TicketOrderStatus.CONFIRMED, TicketOrderStatus.PENDING,
                     TicketOrderStatus.CONFIRMED, TicketOrderStatus.CANCELLED, TicketOrderStatus.EXPIRED],
                    n + event_index,
                )

            order = upsert(TicketOrder, f"order-{order_seq}", defaults={
                "reference": f"MKO-DEMO-{order_seq:06d}",
                "idempotency_key": stable_uuid(f"demo-order-idempotency-{order_seq}"),
                "idempotency_fingerprint": hashlib.sha256(f"demo-order-{order_seq}".encode()).hexdigest(),
                "event": event,
                "buyer": buyer,
                "customer_name": buyer.full_name or buyer.username,
                "customer_email": buyer.email,
                "status": status,
                "total_amount": total,
                "currency": ticket_type.currency,
                "expires_at": created + timedelta(minutes=30) if status in {TicketOrderStatus.PENDING, TicketOrderStatus.EXPIRED} else None,
                "confirmed_at": created + timedelta(minutes=3 + n) if status == TicketOrderStatus.CONFIRMED else None,
                "cancelled_at": created + timedelta(minutes=20) if status == TicketOrderStatus.CANCELLED else None,
            })
            backdate(order, created_at=created, updated_at=min(ctx.as_of, created + timedelta(minutes=40)))
            ctx.orders.append(order)

            item = upsert(TicketOrderItem, f"order-{order_seq}-item", defaults={
                "order": order,
                "ticket_type": ticket_type,
                "quantity": quantity,
                "unit_price": unit_price,
            })
            backdate(item, created_at=created)

            if status == TicketOrderStatus.PENDING:
                reserved_counts[ticket_type.pk] += quantity

            created_tickets = []
            if status == TicketOrderStatus.CONFIRMED:
                for q in range(quantity):
                    ticket = upsert(Ticket, f"order-{order_seq}-ticket-{q}", defaults={
                        "code": stable_uuid(f"ticket-code-{order_seq}-{q}"),
                        "event": event,
                        "ticket_type": ticket_type,
                        "order": order,
                        "owner": buyer,
                        "holder_name": buyer.full_name or buyer.username,
                        "holder_email": buyer.email,
                        "status": TicketStatus.USED if event.end_at < ctx.as_of and (order_seq + q) % 4 != 0 else TicketStatus.VALID,
                        "issued_at": order.confirmed_at or created,
                        "used_at": event.start_at + timedelta(minutes=35 + q * 2) if event.end_at < ctx.as_of and (order_seq + q) % 4 != 0 else None,
                        "cancelled_at": None,
                    })
                    backdate(ticket, created_at=order.confirmed_at or created, updated_at=min(ctx.as_of, (order.confirmed_at or created) + timedelta(days=2)))
                    created_tickets.append(ticket)
                    ctx.tickets.append(ticket)
                    issued_counts[ticket_type.pk] += 1

            if total > 0:
                if status == TicketOrderStatus.CONFIRMED:
                    payment_status = PaymentStatus.SUCCEEDED
                elif status == TicketOrderStatus.PENDING:
                    payment_status = PaymentStatus.PROCESSING if order_seq % 2 else PaymentStatus.PENDING
                elif status == TicketOrderStatus.CANCELLED:
                    payment_status = PaymentStatus.CANCELLED
                else:
                    payment_status = PaymentStatus.FAILED

                refund_this = status == TicketOrderStatus.CONFIRMED and event.end_at < ctx.as_of and order_seq % 19 == 0
                if refund_this:
                    payment_status = PaymentStatus.REFUNDED
                    for ticket in created_tickets:
                        ticket.status = TicketStatus.REFUNDED
                        ticket.save(update_fields=["status"])

                payment = upsert(Payment, f"payment-{order_seq}", defaults={
                    "reference": f"PAY-DEMO-{order_seq:06d}",
                    "order": order,
                    "initiated_by": buyer,
                    "provider": PaymentProvider.SANDBOX,
                    "method": choose([PaymentMethod.MOBILE_MONEY, PaymentMethod.CARD, PaymentMethod.BANK_TRANSFER], order_seq),
                    "status": payment_status,
                    "amount": total,
                    "currency": order.currency,
                    "payer_name": order.customer_name,
                    "payer_email": order.customer_email,
                    "payer_phone": buyer.phone or "",
                    "provider_reference": f"SBX-DEMO-{order_seq:06d}",
                    "idempotency_key": f"demo-payment-{order_seq:06d}",
                    "checkout_url": "",
                    "failure_code": "DECLINED_DEMO" if payment_status == PaymentStatus.FAILED else "",
                    "failure_message": "Paiement de démonstration refusé par le sandbox." if payment_status == PaymentStatus.FAILED else "",
                    "metadata": {"seed": "makolo-demo", "channel": "web"},
                    "processed_at": created + timedelta(minutes=5) if payment_status not in {PaymentStatus.PENDING, PaymentStatus.PROCESSING} else None,
                    "succeeded_at": created + timedelta(minutes=5) if payment_status in {PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED} else None,
                    "failed_at": created + timedelta(minutes=4) if payment_status == PaymentStatus.FAILED else None,
                    "cancelled_at": created + timedelta(minutes=6) if payment_status == PaymentStatus.CANCELLED else None,
                })
                backdate(payment, created_at=created + timedelta(minutes=1), updated_at=min(ctx.as_of, created + timedelta(minutes=8)))
                ctx.payments.append(payment)

                upsert(PaymentEvent, f"payment-event-{order_seq}", defaults={
                    "payment": payment,
                    "provider": PaymentProvider.SANDBOX,
                    "event_id": f"evt_demo_{order_seq:06d}",
                    "event_type": {
                        PaymentStatus.SUCCEEDED: "payment.succeeded",
                        PaymentStatus.REFUNDED: "payment.refunded",
                        PaymentStatus.FAILED: "payment.failed",
                        PaymentStatus.CANCELLED: "payment.cancelled",
                    }.get(payment_status, "payment.processing"),
                    "signature_valid": True,
                    "processed": payment_status not in {PaymentStatus.PENDING, PaymentStatus.PROCESSING},
                    "payload_hash": hashlib.sha256(f"payload-{order_seq}".encode()).hexdigest(),
                    "payload": {"demo": True, "payment_reference": payment.reference, "status": payment_status},
                    "processing_error": "",
                    "received_at": created + timedelta(minutes=5),
                    "processed_at": created + timedelta(minutes=5) if payment_status not in {PaymentStatus.PENDING, PaymentStatus.PROCESSING} else None,
                })

                if refund_this:
                    refund = upsert(Refund, f"refund-{order_seq}", defaults={
                        "reference": f"RFD-DEMO-{order_seq:06d}",
                        "payment": payment,
                        "requested_by": ctx.staff_users[1],
                        "status": RefundStatus.SUCCEEDED,
                        "amount": total,
                        "currency": order.currency,
                        "reason": "Remboursement complet de démonstration après annulation participant.",
                        "provider_reference": f"SBX-RFD-{order_seq:06d}",
                        "idempotency_key": f"demo-refund-{order_seq:06d}",
                        "failure_message": "",
                        "processed_at": min(ctx.as_of, created + timedelta(days=2)),
                    })
                    backdate(refund, created_at=min(ctx.as_of, created + timedelta(days=2)), updated_at=min(ctx.as_of, created + timedelta(days=2, minutes=5)))

    for ticket_type in ctx.ticket_types:
        TicketType.objects.filter(pk=ticket_type.pk).update(
            issued_quantity=issued_counts[ticket_type.pk],
            reserved_quantity=reserved_counts[ticket_type.pk],
        )
        ticket_type.issued_quantity = issued_counts[ticket_type.pk]
        ticket_type.reserved_quantity = reserved_counts[ticket_type.pk]

    _seed_waitlists_and_transfers(ctx, ticket_types_by_event)
    _seed_scanner(ctx)

    ctx.add("events", len(ctx.events))
    ctx.add("orders", len(ctx.orders))
    ctx.add("tickets", len(ctx.tickets))
    ctx.add("payments", len(ctx.payments))


def _seed_waitlists_and_transfers(ctx: SeedContext, ticket_types_by_event) -> None:
    future_public = [
        event for event in ctx.events
        if event.start_at > ctx.as_of and event.status == EventStatus.PUBLISHED and event.visibility == EventVisibility.PUBLIC
    ][:6]
    statuses = [WaitlistStatus.WAITING, WaitlistStatus.OFFERED, WaitlistStatus.CONVERTED, WaitlistStatus.CANCELLED, WaitlistStatus.EXPIRED]
    for i, event in enumerate(future_public):
        tt = ticket_types_by_event[event.pk][0]
        for j in range(5):
            user = ctx.users[(i * 13 + j + 40) % len(ctx.users)]
            status = statuses[j]
            offered_order = None
            if status in {WaitlistStatus.OFFERED, WaitlistStatus.CONVERTED}:
                offered_order = next((o for o in ctx.orders if o.event_id == event.id and o.buyer_id == user.id), None)
            entry = upsert(TicketWaitlistEntry, f"waitlist-{i}-{j}", defaults={
                "ticket_type": tt,
                "user": user,
                "requested_quantity": 1 + (j % 2),
                "status": status,
                "offered_order": offered_order,
                "offered_at": ctx.as_of - timedelta(days=2) if status in {WaitlistStatus.OFFERED, WaitlistStatus.CONVERTED, WaitlistStatus.EXPIRED} else None,
                "offer_expires_at": ctx.as_of + timedelta(hours=12) if status == WaitlistStatus.OFFERED else (ctx.as_of - timedelta(days=1) if status == WaitlistStatus.EXPIRED else None),
                "converted_at": ctx.as_of - timedelta(days=1) if status == WaitlistStatus.CONVERTED else None,
                "cancelled_at": ctx.as_of - timedelta(days=4) if status == WaitlistStatus.CANCELLED else None,
            })
            backdate(entry, created_at=ctx.as_of - timedelta(days=30+i*3+j), updated_at=ctx.as_of - timedelta(days=j))

    transferable = [t for t in ctx.tickets if t.owner_id and t.status in {TicketStatus.VALID, TicketStatus.USED}][:20]
    transfer_statuses = [TransferStatus.ACCEPTED, TransferStatus.PENDING, TransferStatus.DECLINED, TransferStatus.CANCELLED, TransferStatus.EXPIRED]
    for i, ticket in enumerate(transferable):
        sender = ticket.owner
        recipient = ctx.users[(ctx.users.index(sender) + 17 + i) % len(ctx.users)] if sender in ctx.users else ctx.users[(i+17) % len(ctx.users)]
        if recipient.id == sender.id:
            recipient = ctx.users[(i+18) % len(ctx.users)]
        status = transfer_statuses[i % len(transfer_statuses)]
        created = min(ctx.as_of - timedelta(days=2+i), ticket.event.start_at - timedelta(days=10))
        transfer = upsert(TicketTransfer, f"transfer-{i}", defaults={
            "ticket": ticket,
            "sender": sender,
            "recipient": recipient,
            "recipient_email": recipient.email,
            "status": status,
            "expires_at": created + timedelta(days=3),
            "accepted_at": created + timedelta(hours=4) if status == TransferStatus.ACCEPTED else None,
            "declined_at": created + timedelta(hours=6) if status == TransferStatus.DECLINED else None,
            "cancelled_at": created + timedelta(hours=2) if status == TransferStatus.CANCELLED else None,
            "expired_at": created + timedelta(days=3) if status == TransferStatus.EXPIRED else None,
        })
        backdate(transfer, created_at=created, updated_at=min(ctx.as_of, created + timedelta(days=3)))
        if status == TransferStatus.ACCEPTED and ticket.status == TicketStatus.VALID:
            ticket.owner = recipient
            ticket.holder_name = recipient.full_name or recipient.username
            ticket.holder_email = recipient.email
            ticket.save(update_fields=["owner", "holder_name", "holder_email"])


def _seed_scanner(ctx: SeedContext) -> None:
    historical = [e for e in ctx.events if e.end_at < ctx.as_of and e.status == EventStatus.COMPLETED][:12]
    for i, event in enumerate(historical):
        gates = []
        for j, gate_name in enumerate(["Entrée principale", "Accès VIP"]):
            gate = upsert(EventAccessGate, f"event-{event.id}-gate-{j}", defaults={
                "event": event,
                "name": gate_name,
                "slug": f"gate-{j+1}",
                "description": f"{gate_name} — scénario de démonstration.",
                "is_active": True,
                "throughput_target_per_minute": 25 if j == 0 else 12,
                "warning_rejection_rate": 25,
                "priority": 10 + j,
                "notes": "",
                "created_by": event.organizer,
            })
            backdate(gate, created_at=event.start_at - timedelta(days=20), updated_at=event.start_at - timedelta(days=2))
            gates.append(gate)

        assignments = []
        for j in range(2):
            agent = ctx.users[10 + ((i * 2 + j) % max(1, min(14, len(ctx.users)-10)))]
            assignment = upsert(ScannerAssignment, f"event-{event.id}-assignment-{j}", defaults={
                "event": event,
                "agent": agent,
                "assigned_by": event.organizer,
                "access_gate": gates[j],
                "label": gates[j].name,
                "is_active": True,
                "valid_from": event.start_at - timedelta(hours=2),
                "valid_until": event.end_at + timedelta(hours=1),
                "notes": "Affectation de démonstration.",
            })
            backdate(assignment, created_at=event.start_at - timedelta(days=7), updated_at=event.start_at - timedelta(days=1))
            assignments.append(assignment)

        event_tickets = [t for t in ctx.tickets if t.event_id == event.id][:12]
        for j, ticket in enumerate(event_tickets):
            assignment = assignments[j % len(assignments)]
            gate = gates[j % len(gates)]
            scanned_at = event.start_at + timedelta(minutes=15 + j * 3)
            if ticket.status == TicketStatus.USED:
                upsert(ScanLog, f"scan-accepted-{ticket.id}", defaults={
                    "event": event,
                    "ticket": ticket,
                    "scanner": assignment.agent,
                    "assignment": assignment,
                    "access_gate": gate,
                    "result": ScanResult.ACCEPTED,
                    "message": "Accès autorisé.",
                    "qr_fingerprint": hashlib.sha256(ticket.qr_token.encode()).hexdigest(),
                    "client_reference": f"DEMO-SCAN-{stable_token(str(ticket.id), 12)}",
                    "gate": gate.name,
                    "metadata": {"seed": "makolo-demo", "device": "scanner-demo"},
                    "scanned_at": scanned_at,
                })
                if j % 4 == 0:
                    upsert(ScanLog, f"scan-duplicate-{ticket.id}", defaults={
                        "event": event,
                        "ticket": ticket,
                        "scanner": assignment.agent,
                        "assignment": assignment,
                        "access_gate": gate,
                        "result": ScanResult.DUPLICATE,
                        "message": "Billet déjà utilisé.",
                        "qr_fingerprint": hashlib.sha256(ticket.qr_token.encode()).hexdigest(),
                        "client_reference": f"DEMO-DUP-{stable_token(str(ticket.id), 12)}",
                        "gate": gate.name,
                        "metadata": {"seed": "makolo-demo"},
                        "scanned_at": scanned_at + timedelta(minutes=4),
                    })
            elif j % 3 == 0:
                upsert(ScanLog, f"scan-invalid-status-{ticket.id}", defaults={
                    "event": event,
                    "ticket": ticket,
                    "scanner": assignment.agent,
                    "assignment": assignment,
                    "access_gate": gate,
                    "result": ScanResult.INVALID_STATUS,
                    "message": "Billet non valide.",
                    "qr_fingerprint": hashlib.sha256(ticket.qr_token.encode()).hexdigest(),
                    "client_reference": f"DEMO-INV-{stable_token(str(ticket.id), 12)}",
                    "gate": gate.name,
                    "metadata": {"seed": "makolo-demo"},
                    "scanned_at": scanned_at,
                })
