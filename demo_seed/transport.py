from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from activities.models import (
    Activity,
    ActivityStatus,
    ActivityVisibility,
    Occurrence,
    OccurrencePlace,
    OccurrencePlaceRole,
    OccurrenceStatus,
)
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from capacity.models import CapacityPool
from commerce.models import Offer, OfferStatus, PaymentMode
from geography.models import Place, SpacePlace, SpacePlaceRole
from organizations.models import Organization
from scanner.models import ScannerAssignment
from transport.models import TransportDeparture, TransportRoute, TransportRouteStop, TransportService, Vehicle

from .common import SeedContext, stable_uuid, upsert


def seed_transport(ctx: SeedContext) -> None:
    """Canonical-first Transport demo. It intentionally creates no Event."""
    owner = ctx.users[0]
    manager = ctx.users[3]
    finance = ctx.users[4]
    scanner = ctx.users[10]

    space = upsert(
        Organization,
        "mulykap-transport",
        defaults={
            "name": "Mulykap",
            "slug": "mulykap-transport",
            "description": "Transport de personnes entre Lubumbashi, Likasi et Kolwezi.",
            "country": "CD",
            "city": "Lubumbashi",
            "public_profile": True,
            "verification_status": "verified",
            "created_by": owner,
        },
    )
    grant_space_role(profile=owner, space=space, role=SystemRoleCode.SPACE_OWNER, granted_by=owner, source="demo-transport")
    grant_space_role(profile=manager, space=space, role=SystemRoleCode.SPACE_ACTIVITY_MANAGER, granted_by=owner, source="demo-transport")
    grant_space_role(profile=finance, space=space, role=SystemRoleCode.FINANCE, granted_by=owner, source="demo-transport")

    lubumbashi = upsert(
        Place,
        "transport-mulykap-lubumbashi",
        defaults={
            "name": "Agence Mulykap Lubumbashi",
            "address_line": "Centre-ville, Lubumbashi",
            "locality": "Lubumbashi",
            "country_code": "CD",
            "latitude": Decimal("-11.664700"),
            "longitude": Decimal("27.479400"),
            "timezone": "Africa/Lubumbashi",
            "is_active": True,
            "created_by": owner,
        },
    )
    kolwezi = upsert(
        Place,
        "transport-mulykap-kolwezi",
        defaults={
            "name": "Agence Mulykap Kolwezi",
            "address_line": "Centre-ville, Kolwezi",
            "locality": "Kolwezi",
            "country_code": "CD",
            "latitude": Decimal("-10.716700"),
            "longitude": Decimal("25.466700"),
            "timezone": "Africa/Lubumbashi",
            "is_active": True,
            "created_by": owner,
        },
    )
    for position, place in enumerate([lubumbashi, kolwezi], start=1):
        SpacePlace.objects.update_or_create(
            organization=space,
            place=place,
            role=SpacePlaceRole.BRANCH,
            defaults={"is_public": True, "is_active": True, "position": position},
        )

    route = upsert(
        TransportRoute,
        "mulykap-lubumbashi-kolwezi",
        defaults={"space": space, "code": "LUB-KZI", "name": "Lubumbashi → Kolwezi", "active": True},
    )
    TransportRouteStop.objects.update_or_create(
        route=route,
        position=1,
        defaults={"place": lubumbashi, "boarding_allowed": True, "alighting_allowed": False},
    )
    TransportRouteStop.objects.update_or_create(
        route=route,
        position=2,
        defaults={"place": kolwezi, "boarding_allowed": False, "alighting_allowed": True},
    )

    activity = upsert(
        Activity,
        "transport-mulykap-lubumbashi-kolwezi",
        defaults={
            "space": space,
            "created_by": manager,
            "title": "Lubumbashi → Kolwezi",
            "short_description": "Trajet routier Mulykap",
            "description": "Service routier régulier entre Lubumbashi et Kolwezi.",
            "status": ActivityStatus.PUBLISHED,
            "visibility": ActivityVisibility.PUBLIC,
        },
    )
    upsert(
        TransportService,
        "mulykap-lubumbashi-kolwezi",
        defaults={"activity": activity, "route": route, "mode": "road"},
    )

    coach = upsert(
        Vehicle,
        "mulykap-coach-52",
        defaults={
            "space": space,
            "label": "Autocar Mulykap 52",
            "registration": "",
            "vehicle_type": "bus",
            "passenger_capacity": 52,
            "active": True,
        },
    )
    minibus = upsert(
        Vehicle,
        "mulykap-minibus-30",
        defaults={
            "space": space,
            "label": "Minibus Mulykap 30",
            "registration": "",
            "vehicle_type": "minibus",
            "passenger_capacity": 30,
            "active": True,
        },
    )

    base_day = ctx.as_of + timedelta(days=30)
    specs = [
        ("morning", base_day.replace(hour=8, minute=0), base_day.replace(hour=12, minute=0), coach, 52),
        ("afternoon", base_day.replace(hour=14, minute=0), base_day.replace(hour=18, minute=0), coach, 52),
        ("free", (base_day + timedelta(days=1)).replace(hour=8, minute=0), (base_day + timedelta(days=1)).replace(hour=12, minute=0), minibus, 30),
    ]
    departures = []
    for key, start_at, end_at, vehicle, capacity in specs:
        occurrence = upsert(
            Occurrence,
            f"transport-mulykap-{key}",
            defaults={
                "activity": activity,
                "label": "Départ",
                "start_at": start_at,
                "end_at": end_at,
                "timezone": "Africa/Lubumbashi",
                "status": OccurrenceStatus.SCHEDULED,
            },
        )
        OccurrencePlace.objects.update_or_create(
            occurrence=occurrence,
            role=OccurrencePlaceRole.PRIMARY,
            defaults={"place": lubumbashi, "position": 0},
        )
        pool = upsert(
            CapacityPool,
            f"transport-mulykap-{key}",
            defaults={
                "activity": activity,
                "occurrence": occurrence,
                "label": "Voyageurs",
                "total_quantity": capacity,
                "is_active": True,
            },
        )
        departure = upsert(
            TransportDeparture,
            f"transport-mulykap-{key}",
            defaults={
                "occurrence": occurrence,
                "vehicle": vehicle,
                "passenger_capacity_pool": pool,
                "boarding_instructions": "Présentez votre billet Makolo à l’embarquement.",
                "operational_reference": f"MUL-{key.upper()}",
            },
        )
        departures.append((key, departure, pool))

    first_pool = departures[0][2]
    first_occurrence = departures[0][1].occurrence
    upsert(
        Offer,
        "transport-mulykap-morning-standard",
        defaults={
            "activity": activity,
            "occurrence": first_occurrence,
            "capacity_pool": first_pool,
            "name": "Standard",
            "unit_price": Decimal("20.00"),
            "currency": "USD",
            "payment_mode": PaymentMode.UPFRONT,
            "min_quantity": 1,
            "max_quantity": 1,
            "status": OfferStatus.ACTIVE,
        },
    )
    upsert(
        Offer,
        "transport-mulykap-morning-promo",
        defaults={
            "activity": activity,
            "occurrence": first_occurrence,
            "capacity_pool": first_pool,
            "name": "Promo web",
            "unit_price": Decimal("15.00"),
            "currency": "USD",
            "payment_mode": PaymentMode.UPFRONT,
            "min_quantity": 1,
            "max_quantity": 1,
            "status": OfferStatus.ACTIVE,
        },
    )
    upsert(
        Offer,
        "transport-mulykap-afternoon-onsite",
        defaults={
            "activity": activity,
            "occurrence": departures[1][1].occurrence,
            "capacity_pool": departures[1][2],
            "name": "Réserver, payer à l’agence",
            "unit_price": Decimal("20.00"),
            "currency": "USD",
            "payment_mode": PaymentMode.ON_SITE,
            "min_quantity": 1,
            "max_quantity": 1,
            "status": OfferStatus.ACTIVE,
        },
    )
    upsert(
        Offer,
        "transport-mulykap-free",
        defaults={
            "activity": activity,
            "occurrence": departures[2][1].occurrence,
            "capacity_pool": departures[2][2],
            "name": "Navette gratuite",
            "unit_price": Decimal("0.00"),
            "currency": "USD",
            "payment_mode": PaymentMode.NONE,
            "min_quantity": 1,
            "max_quantity": 1,
            "status": OfferStatus.ACTIVE,
        },
    )

    grant_activity_role(profile=scanner, activity=activity, role=SystemRoleCode.ACTIVITY_SCANNER, granted_by=owner, source="demo-transport")
    ScannerAssignment.objects.update_or_create(
        agent=scanner,
        activity=activity,
        occurrence=first_occurrence,
        defaults={"assigned_by": owner, "label": "Embarquement Mulykap", "is_active": True},
    )

    ctx.add("transport_spaces", 1)
    ctx.add("transport_routes", 1)
    ctx.add("transport_departures", len(departures))
    ctx.add("transport_vehicles", 2)
    ctx.add("transport_fares", 4)
