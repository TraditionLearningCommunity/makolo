import importlib
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from commerce.models import PaymentMode
from geography.models import Place, SpacePlace, SpacePlaceRole
from organizations.models import Organization, OrganizationVerificationStatus
from scanner.models import ScannerAssignment
from transport.services import (
    configure_transport_fare,
    create_transport_departure,
    create_transport_route,
    create_transport_service,
    create_transport_vehicle,
    publish_transport_departure,
)


TZ = ZoneInfo("Africa/Lubumbashi")


class Command(BaseCommand):
    help = "Prepare deterministic Transport fixtures after the core E2E reset."

    def handle(self, *args, **options):
        if not getattr(settings, "IS_E2E", False):
            raise CommandError("prepare_transport_e2e est réservé à DJANGO_ENV=e2e.")

        # prepare_e2e flushes the database and replays only the older authority
        # seed steps. Replay the canonical Scanner/Operations authority seed
        # before granting the occurrence-scoped Scanner mandate.
        scanner_authority_seed = importlib.import_module(
            "authorization.migrations.0010_scanner_operations_permissions"
        )
        scanner_authority_seed.seed_permissions(apps, None)

        owner = User.objects.get(username="e2e-owner")
        manager = User.objects.get(username="e2e-event-manager")
        finance = User.objects.get(username="e2e-finance")
        scanner = User.objects.get(username="e2e-scanner")

        space = Organization.objects.create(
            name="Mulykap Transport E2E",
            slug="mulykap-transport-e2e",
            description="Espace Transport canonique déterministe pour Playwright.",
            city="Lubumbashi",
            country="RDC",
            public_profile=True,
            verification_status=OrganizationVerificationStatus.VERIFIED,
            created_by=owner,
        )
        grant_space_role(profile=owner, space=space, role=SystemRoleCode.SPACE_OWNER, granted_by=owner, source="e2e-transport")
        grant_space_role(profile=manager, space=space, role=SystemRoleCode.SPACE_ACTIVITY_MANAGER, granted_by=owner, source="e2e-transport")
        grant_space_role(profile=finance, space=space, role=SystemRoleCode.FINANCE, granted_by=owner, source="e2e-transport")

        origin = Place.objects.create(
            name="Agence Mulykap Lubumbashi E2E",
            address_line="10 avenue du Transport",
            locality="Lubumbashi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
            created_by=owner,
        )
        destination = Place.objects.create(
            name="Agence Mulykap Kolwezi E2E",
            address_line="20 avenue du Transport",
            locality="Kolwezi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
            created_by=owner,
        )
        SpacePlace.objects.create(organization=space, place=origin, role=SpacePlaceRole.BRANCH, is_public=True, position=1)
        SpacePlace.objects.create(organization=space, place=destination, role=SpacePlaceRole.BRANCH, is_public=True, position=2)

        route = create_transport_route(
            space=space,
            name="Lubumbashi → Kolwezi E2E",
            code="E2E-LUB-KZI",
            stops=[origin, destination],
        )
        service = create_transport_service(
            space=space,
            created_by=manager,
            route=route,
            title="Lubumbashi → Kolwezi E2E",
        )
        coach = create_transport_vehicle(
            space=space,
            label="Autocar E2E 52",
            passenger_capacity=52,
        )
        minibus = create_transport_vehicle(
            space=space,
            label="Minibus E2E 30",
            passenger_capacity=30,
        )

        morning = create_transport_departure(
            service=service,
            start_at=datetime(2031, 6, 15, 8, 0, tzinfo=TZ),
            end_at=datetime(2031, 6, 15, 12, 0, tzinfo=TZ),
            timezone_name="Africa/Lubumbashi",
            vehicle=coach,
            capacity=52,
            boarding_instructions="Présentez votre billet Makolo au quai E2E.",
            operational_reference="E2E-MORNING",
        )
        configure_transport_fare(
            departure=morning,
            name="Standard web E2E",
            unit_price=Decimal("20.00"),
            payment_mode=PaymentMode.UPFRONT,
        )
        configure_transport_fare(
            departure=morning,
            name="Promo web E2E",
            unit_price=Decimal("15.00"),
            payment_mode=PaymentMode.UPFRONT,
        )
        publish_transport_departure(departure=morning)

        afternoon = create_transport_departure(
            service=service,
            start_at=datetime(2031, 6, 15, 14, 0, tzinfo=TZ),
            end_at=datetime(2031, 6, 15, 18, 0, tzinfo=TZ),
            timezone_name="Africa/Lubumbashi",
            vehicle=coach,
            capacity=52,
            operational_reference="E2E-AFTERNOON",
        )
        configure_transport_fare(
            departure=afternoon,
            name="Payer à l’agence E2E",
            unit_price=Decimal("20.00"),
            payment_mode=PaymentMode.ON_SITE,
        )
        publish_transport_departure(departure=afternoon)

        free = create_transport_departure(
            service=service,
            start_at=datetime(2031, 6, 16, 8, 0, tzinfo=TZ),
            end_at=datetime(2031, 6, 16, 12, 0, tzinfo=TZ),
            timezone_name="Africa/Lubumbashi",
            vehicle=minibus,
            capacity=30,
            operational_reference="E2E-FREE",
        )
        configure_transport_fare(
            departure=free,
            name="Navette gratuite E2E",
            unit_price=Decimal("0.00"),
            payment_mode=PaymentMode.NONE,
        )
        publish_transport_departure(departure=free)

        grant_activity_role(profile=scanner, activity=service.activity, role=SystemRoleCode.ACTIVITY_SCANNER, granted_by=owner, source="e2e-transport")
        ScannerAssignment.objects.create(
            activity=service.activity,
            occurrence=morning.occurrence,
            agent=scanner,
            assigned_by=owner,
            label="Embarquement Transport E2E",
        )

        self.stdout.write(self.style.SUCCESS("Transport E2E fixtures ready."))
