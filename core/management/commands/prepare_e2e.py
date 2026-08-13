import importlib
from datetime import datetime
from zoneinfo import ZoneInfo

from django.apps import apps
from django.conf import settings
from django.core.management import BaseCommand, CommandError, call_command

from accounts.models import NotificationPreference, User, UserProfile
from authorization.services import ensure_platform_admin_mandate
from events.activity_bridge import sync_event_core
from events.models import Event, EventCategory, EventStatus, EventVenue, EventVisibility, VenueKind
from geography.models import Place
from operations.models import IncidentCategory, IncidentSeverity, IncidentStatus, OperationsIncident
from organizations.models import Organization, OrganizationMembership, OrganizationRole, OrganizationVerificationStatus
from scanner.models import EventAccessGate, ScannerAssignment
from tickets.models import TicketType
from tickets.services import create_order

E2E_PASSWORD = "Makolo-E2E-2026!"
TZ = ZoneInfo("Africa/Lubumbashi")


class Command(BaseCommand):
    help = "Reset and prepare deterministic browser fixtures for DJANGO_ENV=e2e."

    def handle(self, *args, **options):
        if not getattr(settings, "IS_E2E", False):
            raise CommandError("prepare_e2e est réservé à DJANGO_ENV=e2e.")
        call_command("flush", interactive=False, verbosity=0)

        authority_seed = importlib.import_module("authorization.migrations.0002_seed_roles_and_backfill")
        authority_seed.seed_and_backfill(apps, None)
        group_authority_seed = importlib.import_module("authorization.migrations.0003_group_scope")
        group_authority_seed.seed_group_authority(apps, None)
        geography_authority_seed = importlib.import_module("authorization.migrations.0004_space_places_permissions")
        geography_authority_seed.seed_space_place_permissions(apps, None)
        activity_permission_seed = importlib.import_module("authorization.migrations.0006_activity_permissions")
        activity_permission_seed.migrate_activity_permissions(apps, None)
        activity_role_seed = importlib.import_module("authorization.migrations.0007_activity_roles")
        activity_role_seed.migrate_activity_roles(apps, None)

        users = {
            key: self._user(email, username, **flags)
            for key, email, username, flags in [
                ("participant", "participant@e2e.makolo.test", "e2e-participant", {}),
                ("empty", "empty.participant@e2e.makolo.test", "e2e-empty", {}),
                ("visual", "visual.participant@e2e.makolo.test", "e2e-visual", {}),
                ("profile", "profile.user@e2e.makolo.test", "e2e-profile", {}),
                ("reset", "reset.user@e2e.makolo.test", "e2e-reset", {}),
                ("password", "password.user@e2e.makolo.test", "e2e-password", {}),
                ("delete", "delete.me@e2e.makolo.test", "e2e-delete", {}),
                ("sole_owner", "sole.owner@e2e.makolo.test", "e2e-sole-owner", {}),
                ("owner", "owner@e2e.makolo.test", "e2e-owner", {"is_organizer": True}),
                ("event_manager", "event.manager@e2e.makolo.test", "e2e-event-manager", {}),
                ("finance", "finance@e2e.makolo.test", "e2e-finance", {}),
                ("marketing", "marketing@e2e.makolo.test", "e2e-marketing", {}),
                ("scanner", "scanner@e2e.makolo.test", "e2e-scanner", {"is_scanner_agent": True}),
                ("multi", "multi.role@e2e.makolo.test", "e2e-multi", {}),
                ("new_organizer", "new.organizer@e2e.makolo.test", "e2e-new-organizer", {"is_organizer": True}),
                ("staff", "staff@e2e.makolo.test", "e2e-staff", {"is_staff": True}),
            ]
        }
        ensure_platform_admin_mandate(profile=users["staff"], source="e2e-fixture")

        main_org = Organization.objects.create(name="Makolo E2E Events", description="Organisation déterministe pour les parcours navigateur Makolo.", city="Lubumbashi", country="RDC", public_profile=True, verification_status=OrganizationVerificationStatus.VERIFIED, created_by=users["owner"])
        self._membership(main_org, users["owner"], OrganizationRole.OWNER)
        self._membership(main_org, users["event_manager"], OrganizationRole.EVENT_MANAGER)
        self._membership(main_org, users["finance"], OrganizationRole.FINANCE)
        self._membership(main_org, users["marketing"], OrganizationRole.MARKETING)
        self._membership(main_org, users["multi"], OrganizationRole.EVENT_MANAGER)

        finance_org = Organization.objects.create(name="Makolo E2E Finance", public_profile=False, verification_status=OrganizationVerificationStatus.VERIFIED, created_by=users["owner"])
        self._membership(finance_org, users["owner"], OrganizationRole.OWNER)
        self._membership(finance_org, users["multi"], OrganizationRole.FINANCE)
        empty_org = Organization.objects.create(name="Makolo E2E Nouvelle Organisation", description="Organisation sans événement pour tester les états vides.", public_profile=True, verification_status=OrganizationVerificationStatus.VERIFIED, created_by=users["new_organizer"])
        self._membership(empty_org, users["new_organizer"], OrganizationRole.OWNER)
        sole_org = Organization.objects.create(name="Makolo E2E Propriétaire Unique", public_profile=False, verification_status=OrganizationVerificationStatus.VERIFIED, created_by=users["sole_owner"])
        self._membership(sole_org, users["sole_owner"], OrganizationRole.OWNER)

        category = EventCategory.objects.create(name="Culture E2E", description="Catégorie stable pour les tests Playwright.")
        venue_place = Place.objects.create(name="Centre Makolo E2E", address_line="1 avenue des Tests", locality="Lubumbashi", country_code="CD", timezone="Africa/Lubumbashi", created_by=users["owner"])
        venue = EventVenue.objects.create(name="Centre Makolo E2E", kind=VenueKind.PHYSICAL, place=venue_place, address="1 avenue des Tests", city="Lubumbashi", country="RDC")

        paid_event = Event.objects.create(
            organizer=users["owner"], organization=main_org, category=category, venue=venue,
            title="Festival Makolo E2E", short_description="Le parcours critique de billetterie Makolo.",
            description="Événement public stable destiné aux tests de découverte, paiement et contrôle d’accès.",
            status=EventStatus.PUBLISHED, visibility=EventVisibility.PUBLIC,
            start_at=self._dt(2030,6,15,18,0), end_at=self._dt(2030,6,15,23,0),
            registration_start_at=self._dt(2026,1,1,0,0), registration_end_at=self._dt(2030,6,15,17,0),
            timezone="Africa/Lubumbashi", capacity=200, published_at=self._dt(2026,1,1,0,0), metadata={"source":"makolo-e2e"},
        )
        sync_event_core(paid_event)
        paid_type = TicketType.objects.create(event=paid_event, name="Pass standard E2E", description="Billet payant du scénario de bout en bout.", price="12.00", currency="USD", quantity_total=100, min_per_order=1, max_per_order=4, is_active=True, is_public=True)

        visual_event = Event.objects.create(
            organizer=users["owner"], organization=main_org, category=category, venue=venue,
            title="Atelier Makolo Visuel", short_description="Événement stable pour les captures de régression visuelle.",
            description="Un événement gratuit avec un billet déterministe pour les snapshots.", status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC, start_at=self._dt(2030,7,10,9,0), end_at=self._dt(2030,7,10,12,0),
            registration_start_at=self._dt(2026,1,1,0,0), registration_end_at=self._dt(2030,7,10,8,0),
            timezone="Africa/Lubumbashi", capacity=80, published_at=self._dt(2026,1,1,0,0), metadata={"source":"makolo-e2e"},
        )
        sync_event_core(visual_event)
        visual_type = TicketType.objects.create(event=visual_event, name="Invitation E2E", price="0.00", currency="USD", quantity_total=40, min_per_order=1, max_per_order=2, is_active=True, is_public=True)
        create_order(buyer=users["visual"], event=visual_event, customer_name="Visual Participant", customer_email=users["visual"].email, selections=[(visual_type,1)])

        gate = EventAccessGate.objects.create(event=paid_event, name="Entrée E2E", description="Porte du scénario QR end-to-end.", priority=1, created_by=users["owner"])
        ScannerAssignment.objects.create(event=paid_event, agent=users["scanner"], assigned_by=users["owner"], access_gate=gate, label="Contrôle E2E", is_active=True)
        OperationsIncident.objects.create(title="Incident démo E2E à ignorer", category=IncidentCategory.PAYMENT, severity=IncidentSeverity.CRITICAL, status=IncidentStatus.OPEN, description="Incident marqué démo qui ne doit pas dégrader le health réel.", opened_by=users["staff"], metadata={"seed":"makolo-demo","source":"e2e"})
        OperationsIncident.objects.create(title="Incident réel E2E visible", category=IncidentCategory.ACCESS, severity=IncidentSeverity.CRITICAL, status=IncidentStatus.OPEN, description="Incident opérationnel réel attendu dans le navigateur staff.", opened_by=users["staff"], event=paid_event, organization=main_org, metadata={"source":"makolo-e2e"})

        self.stdout.write(self.style.SUCCESS("Makolo E2E fixtures prepared."))
        self.stdout.write(f"Password: {E2E_PASSWORD}")
        self.stdout.write(f"Paid event: {paid_event.slug}")
        self.stdout.write(f"Paid ticket type: {paid_type.pk}")

    def _user(self, email, username, **flags):
        user = User.objects.create_user(email=email, username=username, password=E2E_PASSWORD, first_name=username.replace("e2e-", "").replace("-", " ").title(), **flags)
        UserProfile.objects.get_or_create(user=user); NotificationPreference.objects.get_or_create(user=user); return user

    def _membership(self, organization, user, role):
        return OrganizationMembership.objects.create(organization=organization, user=user, role=role, is_active=True)

    def _dt(self, year, month, day, hour, minute):
        return datetime(year, month, day, hour, minute, tzinfo=TZ)
