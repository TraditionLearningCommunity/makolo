from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from access.models import Access, AccessCredential, AccessStatus, AccessUse, AccessUseResult, CredentialStatus, CredentialType
from accounts.models import NotificationPreference, User
from activities.models import Activity, ActivityStatus, ActivityVisibility, Occurrence, OccurrencePlace, OccurrencePlaceRole, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import ensure_platform_admin_mandate, grant_activity_role, grant_space_role
from automation.models import AutomationRule, DomainAutomationActionKind
from capacity.models import CapacityPool, CapacityReservation, CapacityReservationStatus
from commerce.models import CommerceOrder, CommerceOrderItem, CommerceOrderStatus, Offer, OfferStatus, PaymentMode
from crm.canonical_models import Audience, AudienceMember, AudienceMemberSource, AudienceStatus
from crm.models import CRMContact, ContactSource, MarketingConsent
from domain_events.contracts import DomainEventType
from events.models import Event, EventCategory, EventVenue, VenueKind
from geography.models import Place, SpacePlace, SpacePlaceRole, Zone, ZoneType
from groups.models import Group, GroupMembership, GroupMembershipSource, GroupMembershipStatus, GroupStatus, GroupVisibility
from journeys.models import Journey, JourneyRequest, JourneyStatus, RequestPurpose, RequestStatus, WorkflowKind
from notifications.models import DeliveryChannel, DeliveryStatus, Notification, NotificationCategory, NotificationDelivery, NotificationKind
from operations.models import IncidentCategory, IncidentSeverity, IncidentStatus, OperationsIncident
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus
from payments.models import Payment, PaymentMethod, PaymentProvider, PaymentStatus
from promotions.canonical_models import PromotionOffer, PromotionTargeting
from promotions.models import DiscountType, Promotion, PromotionCode
from scanner.models import EventAccessGate, ScannerAssignment
from tickets.models import TicketType
from transport.models import TransportDeparture, TransportRoute, TransportRouteStop, TransportService, Vehicle

from .common import SeedContext, stable_uuid, upsert

BETA_PERSONAS = {
    "staff": "beta.admin@makolo.test",
    "space_admin": "beta.spaceadmin@makolo.test",
    "event_manager": "beta.eventmanager@makolo.test",
    "transport_operator": "beta.transport@makolo.test",
    "finance": "beta.finance@makolo.test",
    "scanner": "beta.scanner@makolo.test",
    "participant": "beta.participant@makolo.test",
    "marketing": "beta.marketing@makolo.test",
}


def _at(ctx, days, hour):
    return (ctx.as_of + timedelta(days=days)).replace(hour=hour, minute=0, second=0, microsecond=0)


def _weekend(ctx):
    return (5 - ctx.as_of.weekday()) % 7 or 7


def _users(ctx):
    specs = {
        "staff": ("Admin", "Makolo", True, True, False, False),
        "space_admin": ("Amina", "Espace", False, False, True, False),
        "event_manager": ("Grâce", "Événements", False, False, True, False),
        "transport_operator": ("Patrick", "Transport", False, False, True, False),
        "finance": ("Nadine", "Finance", False, False, False, False),
        "scanner": ("Junior", "Contrôle", False, False, False, True),
        "participant": ("Sarah", "Participant", False, False, False, False),
        "marketing": ("Naomi", "Contacts", False, False, False, False),
    }
    result = {}
    for key, (first, last, staff, superuser, organizer, scanner) in specs.items():
        user = upsert(User, f"beta-{key}", defaults={
            "email": BETA_PERSONAS[key], "username": f"beta_{key}", "first_name": first, "last_name": last,
            "language": "fr", "timezone": "Africa/Lubumbashi", "is_active": True, "is_staff": staff,
            "is_superuser": superuser, "is_verified": True, "email_verified": True, "is_organizer": organizer,
            "is_scanner_agent": scanner, "onboarding_completed": True, "onboarding_step": 5,
            "metadata": {"seed": "makolo-beta", "persona": key},
        })
        user.set_password(ctx.demo_password)
        user.save(update_fields=["password"])
        NotificationPreference.objects.update_or_create(user=user, defaults={
            "email_notifications": False, "sms_notifications": False, "push_notifications": False,
            "marketing_notifications": False, "security_notifications": True, "event_notifications": True,
        })
        result[key] = user
    ctx.users, ctx.staff_users = list(result.values()), [result["staff"]]
    ctx.add("beta_personas", len(result))
    return result


def _space(key, name, owner):
    org = upsert(Organization, f"beta-{key}", defaults={
        "name": name, "slug": f"beta-{key}", "description": f"Espace fictif {name}.", "contact_email": f"contact.beta.{key}@makolo.test",
        "country": "CD", "city": "Lubumbashi", "public_profile": True, "verification_status": "verified", "created_by": owner,
    })
    team = upsert(Team, f"beta-{key}", defaults={"organization": org, "name": "Équipe bêta", "is_default": True, "is_active": True})
    return org, team


def _member(team, user, inviter):
    upsert(TeamMembership, f"beta-{team.pk}-{user.pk}", defaults={"team": team, "user": user, "status": TeamMembershipStatus.ACTIVE, "invited_by": inviter})


def _place(key, name, locality, lat, lon, owner):
    return upsert(Place, f"beta-{key}", defaults={
        "name": name, "address_line": f"Centre-ville, {locality}", "locality": locality,
        "administrative_area": "Lualaba" if locality == "Kolwezi" else "Haut-Katanga", "country_code": "CD",
        "latitude": Decimal(lat) if lat else None, "longitude": Decimal(lon) if lon else None,
        "timezone": "Africa/Lubumbashi", "is_active": True, "created_by": owner,
    })


def _event(ctx, key, space, manager, category, place, title, days, hour, *, status=ActivityStatus.PUBLISHED, visibility=ActivityVisibility.PUBLIC, capacity=80, price=None, mode=PaymentMode.NONE):
    activity = upsert(Activity, f"beta-event-{key}", defaults={
        "space": space, "created_by": manager, "title": title, "slug": f"beta-event-{key}",
        "short_description": f"Scénario bêta — {title}", "description": "Événement fictif pour la bêta Makolo.",
        "status": status, "visibility": visibility,
    })
    start = _at(ctx, days, hour)
    occ = upsert(Occurrence, f"beta-event-{key}", defaults={
        "activity": activity, "label": "Date principale", "start_at": start, "end_at": start + timedelta(hours=4),
        "timezone": "Africa/Lubumbashi", "status": OccurrenceStatus.COMPLETED if status == ActivityStatus.COMPLETED else (OccurrenceStatus.CANCELLED if status == ActivityStatus.CANCELLED else OccurrenceStatus.SCHEDULED),
    })
    OccurrencePlace.objects.update_or_create(occurrence=occ, role=OccurrencePlaceRole.PRIMARY, defaults={"place": place, "position": 0})
    venue = upsert(EventVenue, f"beta-event-{key}", defaults={"name": place.name, "kind": VenueKind.PHYSICAL, "place": place, "is_active": True})
    event = upsert(Event, f"beta-event-{key}", defaults={
        "activity": activity, "category": category, "venue": venue, "slug": f"beta-{key}",
        "registration_start_at": ctx.as_of - timedelta(days=7), "registration_end_at": start - timedelta(hours=1),
        "published_at": ctx.as_of - timedelta(days=7) if status == ActivityStatus.PUBLISHED else None,
        "cancelled_at": ctx.as_of if status == ActivityStatus.CANCELLED else None, "metadata": {"seed": "makolo-beta", "scenario": key},
    })
    pool = offer = ticket_type = None
    if capacity is not None:
        pool = upsert(CapacityPool, f"beta-event-{key}", defaults={
            "activity": activity, "occurrence": occ, "label": "Places", "total_quantity": capacity, "is_active": True,
            "source_key": f"event:{event.pk}:capacity",
        })
    if price is not None:
        offer = upsert(Offer, f"beta-event-{key}", defaults={
            "activity": activity, "occurrence": occ, "capacity_pool": pool, "name": "Standard", "unit_price": Decimal(price),
            "currency": "USD", "payment_mode": mode, "available_from": ctx.as_of - timedelta(days=7),
            "available_until": start - timedelta(hours=1), "min_quantity": 1, "max_quantity": 4,
            "status": OfferStatus.ACTIVE, "source_key": f"beta:event:{key}:offer",
        })
        ticket_type = upsert(TicketType, f"beta-event-{key}", defaults={
            "event": event, "offer": offer, "capacity_pool": pool, "name": "Standard", "slug": "standard",
            "description": "Projection Event du tarif canonique.", "is_public": True,
        })
    return {"activity": activity, "occurrence": occ, "event": event, "pool": pool, "offer": offer, "ticket_type": ticket_type}


def _events(ctx, users, space, places):
    category = upsert(EventCategory, "beta", defaults={"name": "Communauté bêta", "slug": "beta", "is_active": True})
    w = _weekend(ctx)
    specs = [
        ("today", "Rencontre Makolo aujourd’hui", 0, 20, 60, "0.00", PaymentMode.NONE, ActivityStatus.PUBLISHED, ActivityVisibility.PUBLIC, "lub"),
        ("free", "Atelier communauté gratuit", 1, 17, 40, "0.00", PaymentMode.NONE, ActivityStatus.PUBLISHED, ActivityVisibility.PUBLIC, "lub"),
        ("paid", "Forum créatif Makolo", max(2, w), 10, 80, "25.00", PaymentMode.UPFRONT, ActivityStatus.PUBLISHED, ActivityVisibility.PUBLIC, "lub"),
        ("cancelled", "Événement annulé — bêta", 5, 14, 30, None, PaymentMode.NONE, ActivityStatus.CANCELLED, ActivityVisibility.PUBLIC, "lik"),
        ("full", "Masterclass complète", 7, 9, 2, "10.00", PaymentMode.UPFRONT, ActivityStatus.PUBLISHED, ActivityVisibility.PUBLIC, "kol"),
        ("private", "Session privée bêta", 10, 16, 20, None, PaymentMode.NONE, ActivityStatus.PUBLISHED, ActivityVisibility.PRIVATE, "lub"),
        ("unlisted", "Rencontre non répertoriée bêta", 12, 16, 20, None, PaymentMode.NONE, ActivityStatus.PUBLISHED, ActivityVisibility.UNLISTED, "lub"),
        ("invitation", "Dîner partenaires sur invitation", 14, 19, 30, None, PaymentMode.NONE, ActivityStatus.PUBLISHED, ActivityVisibility.PUBLIC, "lub"),
        ("no-commerce", "Rencontre publique sans billetterie", 21, 15, None, None, PaymentMode.NONE, ActivityStatus.PUBLISHED, ActivityVisibility.PUBLIC, "text"),
        ("horizon", "Sommet Makolo à 30 jours", 30, 10, 120, "15.00", PaymentMode.UPFRONT, ActivityStatus.PUBLISHED, ActivityVisibility.PUBLIC, "kol"),
        ("history", "Rencontre Makolo passée", -7, 18, 50, "0.00", PaymentMode.NONE, ActivityStatus.COMPLETED, ActivityVisibility.PUBLIC, "lub"),
    ]
    result = {}
    for key, title, days, hour, capacity, price, mode, status, visibility, place_key in specs:
        result[key] = _event(ctx, key, space, users["event_manager"], category, places[place_key], title, days, hour, status=status, visibility=visibility, capacity=capacity, price=price, mode=mode)
    ctx.events = [s["event"] for s in result.values()]
    ctx.ticket_types = [s["ticket_type"] for s in result.values() if s["ticket_type"]]
    ctx.add("beta_events", len(result))
    return result


def _transport(ctx, users, space, places):
    route_data = {}
    for key, code, origin, destination in [("lub-kol", "LUB-KOL", places["lub"], places["kol"]), ("kol-lub", "KOL-LUB", places["kol"], places["lub"])]:
        route = upsert(TransportRoute, f"beta-{key}", defaults={"space": space, "code": code, "name": f"{origin.locality} → {destination.locality}", "active": True})
        TransportRouteStop.objects.update_or_create(route=route, position=1, defaults={"place": origin, "boarding_allowed": True, "alighting_allowed": False})
        TransportRouteStop.objects.update_or_create(route=route, position=2, defaults={"place": destination, "boarding_allowed": False, "alighting_allowed": True})
        activity = upsert(Activity, f"beta-transport-{key}", defaults={
            "space": space, "created_by": users["transport_operator"], "title": route.name, "slug": f"beta-transport-{key}",
            "short_description": "Trajet routier fictif de la bêta Makolo.", "description": "Transport canonique indépendant d’Events.",
            "status": ActivityStatus.PUBLISHED, "visibility": ActivityVisibility.PUBLIC,
        })
        service = upsert(TransportService, f"beta-{key}", defaults={"activity": activity, "route": route, "mode": "road"})
        route_data[key] = (route, activity, service, origin)
    coach = upsert(Vehicle, "beta-coach", defaults={"space": space, "label": "Autocar bêta 40", "vehicle_type": "bus", "passenger_capacity": 40, "active": True})
    mini = upsert(Vehicle, "beta-mini", defaults={"space": space, "label": "Minibus bêta 18", "vehicle_type": "minibus", "passenger_capacity": 18, "active": True})
    w = _weekend(ctx)
    specs = [
        ("history", "lub-kol", -7, 8, coach, 40, "20", PaymentMode.UPFRONT), ("today", "lub-kol", 0, 18, coach, 40, "20", PaymentMode.UPFRONT),
        ("tomorrow", "kol-lub", 1, 8, mini, 18, "18", PaymentMode.ON_SITE), ("weekend", "lub-kol", max(2, w), 7, coach, 40, "20", PaymentMode.UPFRONT),
        ("full", "kol-lub", 7, 14, mini, 1, "18", PaymentMode.UPFRONT), ("week2", "lub-kol", 14, 8, coach, 40, "20", PaymentMode.UPFRONT),
        ("week3", "kol-lub", 21, 8, mini, 18, "18", PaymentMode.ON_SITE), ("month", "lub-kol", 30, 8, coach, 40, "20", PaymentMode.UPFRONT),
    ]
    result = {}
    for key, route_key, days, hour, vehicle, capacity, price, mode in specs:
        route, activity, service, origin = route_data[route_key]
        start = _at(ctx, days, hour)
        occ = upsert(Occurrence, f"beta-transport-{key}", defaults={"activity": activity, "label": "Départ", "start_at": start, "end_at": start + timedelta(hours=4), "timezone": "Africa/Lubumbashi", "status": OccurrenceStatus.COMPLETED if days < 0 else OccurrenceStatus.SCHEDULED})
        OccurrencePlace.objects.update_or_create(occurrence=occ, role=OccurrencePlaceRole.PRIMARY, defaults={"place": origin, "position": 0})
        pool = upsert(CapacityPool, f"beta-transport-{key}", defaults={"activity": activity, "occurrence": occ, "label": "Voyageurs", "total_quantity": capacity, "is_active": True, "source_key": f"beta:transport:{key}:capacity"})
        departure = upsert(TransportDeparture, f"beta-{key}", defaults={"occurrence": occ, "vehicle": vehicle, "passenger_capacity_pool": pool, "boarding_instructions": "Présentez votre billet Makolo.", "operational_reference": f"BETA-{key.upper()}"})
        offer = upsert(Offer, f"beta-transport-{key}", defaults={"activity": activity, "occurrence": occ, "capacity_pool": pool, "name": "Tarif standard", "unit_price": Decimal(price), "currency": "USD", "payment_mode": mode, "available_from": ctx.as_of - timedelta(days=7), "available_until": start - timedelta(hours=1), "min_quantity": 1, "max_quantity": 1, "status": OfferStatus.ACTIVE, "source_key": f"beta:transport:{key}:offer"})
        result[key] = {"activity": activity, "occurrence": occ, "pool": pool, "departure": departure, "offer": offer}
    ctx.add("beta_transport_departures", len(result))
    return result


def _journey(ctx, key, user, scenario, workflow, status):
    return upsert(Journey, f"beta-{key}", defaults={
        "initiated_by": user, "beneficiary": user, "activity": scenario["activity"], "occurrence": scenario["occurrence"],
        "workflow": workflow, "status": status, "expires_at": scenario["occurrence"].start_at if status in {JourneyStatus.DRAFT, JourneyStatus.PENDING_PAYMENT} else None,
        "submitted_at": ctx.as_of - timedelta(days=2) if status != JourneyStatus.DRAFT else None,
        "confirmed_at": ctx.as_of - timedelta(days=1) if status in {JourneyStatus.CONFIRMED, JourneyStatus.FULFILLED} else None,
        "fulfilled_at": ctx.as_of - timedelta(hours=12) if status == JourneyStatus.FULFILLED else None,
    })


def _reserve(ctx, key, journey, pool, qty=1):
    return upsert(CapacityReservation, f"beta-{key}", defaults={"pool": pool, "journey": journey, "quantity": qty, "status": CapacityReservationStatus.COMMITTED, "committed_at": ctx.as_of - timedelta(days=1), "source_key": f"beta:{key}"})


def _order(ctx, key, journey, buyer, space, offer, reservation):
    order = upsert(CommerceOrder, f"beta-{key}", defaults={
        "reference": f"BETA-{key.upper()[:18]}", "journey": journey, "buyer": buyer, "payee_space": space,
        "status": CommerceOrderStatus.CONFIRMED, "currency": offer.currency, "payment_mode": offer.payment_mode,
        "subtotal": offer.unit_price, "discount_total": Decimal("0"), "total": offer.unit_price,
        "confirmed_at": ctx.as_of - timedelta(days=1), "idempotency_key": f"beta:{key}", "source_key": f"beta:{key}",
    })
    upsert(CommerceOrderItem, f"beta-{key}", defaults={"order": order, "offer": offer, "beneficiary": buyer, "capacity_reservation": reservation, "quantity": 1, "label_snapshot": offer.name, "unit_price": offer.unit_price, "line_subtotal": offer.unit_price, "discount_total": Decimal("0"), "line_total": offer.unit_price})
    return order


def _payment(ctx, key, order, buyer):
    return upsert(Payment, f"beta-{key}", defaults={
        "reference": f"PAY-BETA-{key.upper()[:14]}", "commerce_order": order, "initiated_by": buyer,
        "provider": PaymentProvider.SANDBOX, "method": PaymentMethod.MOBILE_MONEY, "status": PaymentStatus.SUCCEEDED,
        "amount": order.total, "currency": order.currency, "payer_name": buyer.full_name, "payer_email": buyer.email,
        "provider_reference": f"sandbox-beta-{key}", "idempotency_key": f"beta-payment:{key}", "metadata": {"seed": "makolo-beta"},
        "processed_at": ctx.as_of - timedelta(days=1), "succeeded_at": ctx.as_of - timedelta(days=1),
    })


def _access(ctx, key, user, journey, scenario, status=AccessStatus.VALID, used=False):
    access = upsert(Access, f"beta-{key}", defaults={"beneficiary": user, "activity": scenario["activity"], "occurrence": scenario["occurrence"], "journey": journey, "status": status, "single_use": True, "source_key": f"beta:{key}", "valid_from": scenario["occurrence"].start_at - timedelta(hours=2), "valid_until": scenario["occurrence"].end_at + timedelta(hours=2)})
    credential = upsert(AccessCredential, f"beta-{key}", defaults={"access": access, "credential_type": CredentialType.QR, "status": CredentialStatus.ACTIVE, "public_id": stable_uuid(f"beta-public-{key}"), "version": 1, "issued_at": ctx.as_of - timedelta(days=1)})
    if used:
        upsert(AccessUse, f"beta-{key}", defaults={"access": access, "credential": credential, "occurrence": scenario["occurrence"], "result": AccessUseResult.ACCEPTED, "source": "beta-seed-history", "used_at": scenario["occurrence"].start_at + timedelta(minutes=20)})
    return access


def _flows(ctx, users, event_space, transport_space, events, trips):
    p = users["participant"]
    j = _journey(ctx, "event-free", p, events["free"], WorkflowKind.REGISTRATION, JourneyStatus.CONFIRMED); _reserve(ctx, "event-free", j, events["free"]["pool"]); _access(ctx, "event-free", p, j, events["free"])
    j = _journey(ctx, "event-paid", p, events["paid"], WorkflowKind.PURCHASE, JourneyStatus.CONFIRMED); r = _reserve(ctx, "event-paid", j, events["paid"]["pool"]); o = _order(ctx, "event-paid", j, p, event_space, events["paid"]["offer"], r); _payment(ctx, "event-paid", o, p); _access(ctx, "event-paid", p, j, events["paid"])
    j = _journey(ctx, "event-invitation", p, events["invitation"], WorkflowKind.INVITATION, JourneyStatus.PENDING_APPROVAL)
    upsert(JourneyRequest, "beta-invitation", defaults={"journey": j, "requester": users["event_manager"], "purpose": RequestPurpose.INVITATION, "status": RequestStatus.PENDING, "message": "Invitation bêta à accepter.", "submitted_at": ctx.as_of - timedelta(days=1), "expires_at": events["invitation"]["occurrence"].start_at - timedelta(hours=2)})
    guest = users["marketing"]; j2 = _journey(ctx, "event-invitation-accepted", guest, events["invitation"], WorkflowKind.INVITATION, JourneyStatus.CONFIRMED); _reserve(ctx, "event-invitation-accepted", j2, events["invitation"]["pool"]); _access(ctx, "event-invitation-accepted", guest, j2, events["invitation"])
    _journey(ctx, "event-draft", p, events["no-commerce"], WorkflowKind.REGISTRATION, JourneyStatus.DRAFT)
    j = _journey(ctx, "event-history", p, events["history"], WorkflowKind.REGISTRATION, JourneyStatus.FULFILLED); _reserve(ctx, "event-history", j, events["history"]["pool"]); _access(ctx, "event-history", p, j, events["history"], AccessStatus.USED, True)
    j = _journey(ctx, "transport-online", p, trips["weekend"], WorkflowKind.RESERVATION, JourneyStatus.CONFIRMED); r = _reserve(ctx, "transport-online", j, trips["weekend"]["pool"]); o = _order(ctx, "transport-online", j, p, transport_space, trips["weekend"]["offer"], r); _payment(ctx, "transport-online", o, p); _access(ctx, "transport-online", p, j, trips["weekend"])
    j = _journey(ctx, "transport-onsite", p, trips["tomorrow"], WorkflowKind.RESERVATION, JourneyStatus.CONFIRMED); r = _reserve(ctx, "transport-onsite", j, trips["tomorrow"]["pool"]); _order(ctx, "transport-onsite", j, p, transport_space, trips["tomorrow"]["offer"], r); _access(ctx, "transport-onsite", p, j, trips["tomorrow"])
    for suffix, user in [("a", users["space_admin"]), ("b", users["marketing"])]:
        j = _journey(ctx, f"event-full-{suffix}", user, events["full"], WorkflowKind.PURCHASE, JourneyStatus.CONFIRMED); _reserve(ctx, f"event-full-{suffix}", j, events["full"]["pool"])
    j = _journey(ctx, "transport-full", users["space_admin"], trips["full"], WorkflowKind.RESERVATION, JourneyStatus.CONFIRMED); _reserve(ctx, "transport-full", j, trips["full"]["pool"])


def _scanner(ctx, users, events, trips):
    scanner = users["scanner"]
    grant_activity_role(profile=scanner, activity=events["paid"]["activity"], role=SystemRoleCode.ACTIVITY_SCANNER, granted_by=users["space_admin"], source="makolo-beta")
    gate = upsert(EventAccessGate, "beta-gate", defaults={"event": events["paid"]["event"], "name": "Entrée bêta", "slug": "entree-beta", "is_active": True, "created_by": users["event_manager"]})
    upsert(ScannerAssignment, "beta-event", defaults={"activity": events["paid"]["activity"], "occurrence": events["paid"]["occurrence"], "event": events["paid"]["event"], "agent": scanner, "assigned_by": users["event_manager"], "access_gate": gate, "label": "Entrée bêta", "is_active": True, "valid_from": ctx.as_of - timedelta(days=1), "valid_until": events["paid"]["occurrence"].end_at + timedelta(hours=1)})
    grant_activity_role(profile=scanner, activity=trips["weekend"]["activity"], role=SystemRoleCode.ACTIVITY_SCANNER, granted_by=users["space_admin"], source="makolo-beta")
    upsert(ScannerAssignment, "beta-transport", defaults={"activity": trips["weekend"]["activity"], "occurrence": trips["weekend"]["occurrence"], "agent": scanner, "assigned_by": users["transport_operator"], "label": "Embarquement bêta", "is_active": True, "valid_from": ctx.as_of - timedelta(days=1), "valid_until": trips["weekend"]["occurrence"].end_at + timedelta(hours=1)})
    for key, scenario in [("event", events["paid"]), ("transport", trips["weekend"])]:
        j = _journey(ctx, f"scanner-smoke-{key}", users["space_admin"], scenario, WorkflowKind.REGISTRATION if key == "event" else WorkflowKind.RESERVATION, JourneyStatus.CONFIRMED); _access(ctx, f"scanner-smoke-{key}", users["space_admin"], j, scenario)
    ctx.add("beta_scanner_assignments", 2)


def _notifications(ctx, users):
    p = users["participant"]
    specs = [("event", NotificationKind.TICKETS_ISSUED, NotificationCategory.TICKET, "Billet disponible", "Votre billet Event est disponible.", "/me/accesses/", None), ("transport", NotificationKind.TICKETS_ISSUED, NotificationCategory.TICKET, "Billet disponible", "Votre billet de trajet est disponible.", "/me/accesses/", ctx.as_of - timedelta(hours=1)), ("action", NotificationKind.SYSTEM, NotificationCategory.SYSTEM, "Invitation à traiter", "Une invitation vous attend dans Mes démarches.", "/me/journeys/", None)]
    for key, kind, category, title, message, url, read_at in specs:
        n = upsert(Notification, f"beta-{key}", defaults={"recipient": p, "kind": kind, "category": category, "title": title, "message": message, "action_url": url, "dedup_key": f"beta-notification-{key}", "metadata": {"seed": "makolo-beta"}, "read_at": read_at})
        upsert(NotificationDelivery, f"beta-{key}", defaults={"notification": n, "channel": DeliveryChannel.EMAIL, "destination": p.email, "status": DeliveryStatus.SKIPPED, "scheduled_for": ctx.as_of, "attempts": 0, "max_attempts": 3, "skipped_reason": "Delivery externe neutralisée dans le seed bêta."})
    ctx.add("beta_notifications", len(specs))


def _console_data(ctx, users, space, paid):
    p = users["participant"]
    contacts = []
    for key, user, email, name, consent in [("participant", p, p.email, p.full_name, MarketingConsent.UNKNOWN), ("subscribed", None, "beta.contact.subscribed@makolo.test", "Contact abonné bêta", MarketingConsent.SUBSCRIBED), ("unsubscribed", None, "beta.contact.unsubscribed@makolo.test", "Contact désabonné bêta", MarketingConsent.UNSUBSCRIBED)]:
        contacts.append(upsert(CRMContact, f"beta-{key}", defaults={"organization": space, "user": user, "email": email, "name": name, "source": ContactSource.MANUAL, "marketing_consent": consent, "first_seen_at": ctx.as_of - timedelta(days=20), "last_seen_at": ctx.as_of, "metadata": {"seed": "makolo-beta"}}))
    audience = upsert(Audience, "beta-active", defaults={"organization": space, "name": "Participants bêta actifs", "description": "L’appartenance ne vaut pas consentement marketing.", "status": AudienceStatus.ACTIVE, "created_by": users["marketing"]})
    upsert(AudienceMember, "beta-participant", defaults={"audience": audience, "profile": p, "source": AudienceMemberSource.MANUAL})
    promo = upsert(Promotion, "beta-active", defaults={"organization": space, "name": "Bêta 10%", "description": "Promotion fictive active.", "discount_type": DiscountType.PERCENT, "discount_value": Decimal("10"), "starts_at": ctx.as_of - timedelta(days=2), "ends_at": ctx.as_of + timedelta(days=10), "max_redemptions": 50, "is_active": True, "created_by": users["marketing"]})
    upsert(PromotionCode, "beta-active", defaults={"promotion": promo, "code": "BETA10", "starts_at": ctx.as_of - timedelta(days=2), "ends_at": ctx.as_of + timedelta(days=10), "is_active": True, "created_by": users["marketing"]})
    upsert(PromotionTargeting, "beta-active", defaults={"promotion": promo, "activity": paid["activity"], "audience": audience})
    upsert(PromotionOffer, "beta-active", defaults={"promotion": promo, "offer": paid["offer"], "source": "canonical"})
    upsert(Promotion, "beta-expired", defaults={"organization": space, "name": "Bêta expirée", "discount_type": DiscountType.PERCENT, "discount_value": Decimal("5"), "starts_at": ctx.as_of - timedelta(days=30), "ends_at": ctx.as_of - timedelta(days=1), "is_active": False, "created_by": users["marketing"]})
    group = upsert(Group, "beta-community", defaults={"name": "Communauté bêta Events", "slug": "beta-event-community", "description": "Groupe fictif de l’Espace.", "space": space, "created_by": users["event_manager"], "status": GroupStatus.ACTIVE, "visibility": GroupVisibility.SPACE})
    for key in ["participant", "marketing", "event_manager"]:
        upsert(GroupMembership, f"beta-{key}", defaults={"group": group, "profile": users[key], "status": GroupMembershipStatus.ACTIVE, "source": GroupMembershipSource.MANUAL, "joined_at": ctx.as_of - timedelta(days=7)})
    upsert(AutomationRule, "beta-disabled", defaults={"space": space, "activity": paid["activity"], "name": "Rappel billet bêta (désactivé)", "trigger_event_type": DomainEventType.ACCESS_ISSUED, "conditions": {}, "action_kind": DomainAutomationActionKind.NOTIFICATION, "action_config": {"recipient": "beneficiary", "title": "Billet disponible", "message": "Votre billet Makolo est disponible.", "category": "ticket", "queue_email": False}, "is_active": False, "created_by": users["event_manager"]})
    for key, status, title, resolution in [("open", IncidentStatus.OPEN, "Incident bêta ouvert", ""), ("investigating", IncidentStatus.INVESTIGATING, "Incident bêta en cours", ""), ("resolved", IncidentStatus.RESOLVED, "Incident bêta résolu", "Résolution fictive validée.")]:
        upsert(OperationsIncident, f"beta-{key}", defaults={"title": title, "category": IncidentCategory.SUPPORT, "severity": IncidentSeverity.LOW, "status": status, "organization": space, "activity": paid["activity"], "occurrence": paid["occurrence"], "description": "Incident fictif pour Operations.", "resolution": resolution, "opened_by": users["staff"], "assigned_to": users["staff"], "detected_at": ctx.as_of - timedelta(days=2), "resolved_at": ctx.as_of - timedelta(days=1) if status == IncidentStatus.RESOLVED else None, "metadata": {"seed": "makolo-beta"}})
    ctx.contacts, ctx.promotions = contacts, [promo]
    for label, count in [("beta_contacts", 3), ("beta_audiences", 1), ("beta_promotions", 2), ("beta_groups", 1), ("beta_automation_rules", 1), ("beta_operations_incidents", 3)]: ctx.add(label, count)


def seed_beta(ctx: SeedContext) -> None:
    users = _users(ctx)
    ensure_platform_admin_mandate(profile=users["staff"], source="makolo-beta")
    event_space, event_team = _space("events", "Makolo Beta Events", users["space_admin"])
    transport_space, transport_team = _space("transport", "Makolo Beta Transport", users["space_admin"])
    ctx.organizations = [event_space, transport_space]
    for team, keys in [(event_team, ["space_admin", "event_manager", "finance", "marketing", "scanner"]), (transport_team, ["space_admin", "transport_operator", "finance", "scanner"])]:
        for key in keys: _member(team, users[key], users["space_admin"])
    for space in [event_space, transport_space]: grant_space_role(profile=users["space_admin"], space=space, role=SystemRoleCode.SPACE_OWNER, granted_by=users["staff"], source="makolo-beta")
    grant_space_role(profile=users["event_manager"], space=event_space, role=SystemRoleCode.SPACE_ACTIVITY_MANAGER, granted_by=users["space_admin"], source="makolo-beta")
    grant_space_role(profile=users["transport_operator"], space=transport_space, role=SystemRoleCode.SPACE_ACTIVITY_MANAGER, granted_by=users["space_admin"], source="makolo-beta")
    for space in [event_space, transport_space]: grant_space_role(profile=users["finance"], space=space, role=SystemRoleCode.FINANCE, granted_by=users["space_admin"], source="makolo-beta")
    grant_space_role(profile=users["marketing"], space=event_space, role=SystemRoleCode.MARKETING, granted_by=users["space_admin"], source="makolo-beta")
    places = {"lub": _place("lub", "Centre Makolo Lubumbashi", "Lubumbashi", "-11.664700", "27.479400", users["space_admin"]), "kol": _place("kol", "Agence Makolo Kolwezi", "Kolwezi", "-10.716700", "25.466700", users["space_admin"]), "lik": _place("lik", "Maison Makolo Likasi", "Likasi", "-10.981400", "26.733300", users["space_admin"]), "text": _place("text", "Lieu sans coordonnées — bêta", "Lubumbashi", None, None, users["space_admin"])}
    for space, keys in [(event_space, ["lub", "kol", "lik", "text"]), (transport_space, ["lub", "kol"])]:
        for i, key in enumerate(keys): SpacePlace.objects.update_or_create(organization=space, place=places[key], role=SpacePlaceRole.SERVICE_POINT, defaults={"public_label": places[key].name, "is_primary": i == 0, "is_public": True, "is_active": True, "position": i})
    upsert(Zone, "beta-nearby", defaults={"name": "Autour de Lubumbashi — bêta", "zone_type": ZoneType.RADIUS, "country_code": "CD", "administrative_area": "Haut-Katanga", "locality": "Lubumbashi", "center_place": places["lub"], "radius_m": 25000, "is_active": True, "created_by": users["space_admin"]})
    events = _events(ctx, users, event_space, places)
    trips = _transport(ctx, users, transport_space, places)
    _flows(ctx, users, event_space, transport_space, events, trips)
    _scanner(ctx, users, events, trips)
    _notifications(ctx, users)
    _console_data(ctx, users, event_space, events["paid"])
    for label, count in [("beta_spaces", 2), ("beta_places", 4), ("beta_journeys", Journey.objects.filter(initiated_by__email__in=BETA_PERSONAS.values()).count()), ("beta_commerce_orders", CommerceOrder.objects.filter(source_key__startswith="beta:").count()), ("beta_payments", Payment.objects.filter(metadata__seed="makolo-beta").count()), ("beta_accesses", Access.objects.filter(source_key__startswith="beta:").count())]: ctx.add(label, count)
