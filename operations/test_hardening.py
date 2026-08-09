from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization, OrganizationVerificationStatus
from payments.models import Payment, PaymentProvider, PaymentStatus
from tickets.models import TicketOrder, TicketOrderStatus

from .models import IncidentCategory, IncidentSeverity, IncidentStatus, OperationsIncident
from .services import build_operations_overview, create_incident


User = get_user_model()


class OperationsHardeningTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.staff = User.objects.create_user(
            username="ops-hardening-staff",
            email="ops-hardening-staff@test.local",
            password="Strong-password-2026!",
            is_staff=True,
        )
        self.buyer = User.objects.create_user(
            username="ops-hardening-buyer",
            email="ops-hardening-buyer@test.local",
            password="Strong-password-2026!",
        )
        self.organization = Organization.objects.create(
            name="Operations Hardening Org",
            verification_status=OrganizationVerificationStatus.VERIFIED,
            created_by=self.staff,
        )
        self.event = Event.objects.create(
            organizer=self.staff,
            organization=self.organization,
            title="Operations Hardening Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=self.now + timedelta(days=2),
            end_at=self.now + timedelta(days=2, hours=2),
        )

    def test_model_rejects_resolved_incident_without_resolution(self):
        incident = OperationsIncident(
            title="Résolution obligatoire",
            category=IncidentCategory.OTHER,
            severity=IncidentSeverity.MEDIUM,
            status=IncidentStatus.RESOLVED,
            description="Test de frontière modèle.",
            opened_by=self.staff,
        )
        with self.assertRaises(ValidationError):
            incident.full_clean()

    def test_incident_rejects_payment_from_another_organization(self):
        other_organization = Organization.objects.create(
            name="Operations Other Org",
            verification_status=OrganizationVerificationStatus.VERIFIED,
            created_by=self.staff,
        )
        other_event = Event.objects.create(
            organizer=self.staff,
            organization=other_organization,
            title="Operations Other Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=self.now + timedelta(days=3),
            end_at=self.now + timedelta(days=3, hours=2),
        )
        order = TicketOrder.objects.create(
            event=other_event,
            buyer=self.buyer,
            customer_name="Hardening Buyer",
            customer_email=self.buyer.email,
            status=TicketOrderStatus.PENDING,
            total_amount=Decimal("10.00"),
            currency="USD",
        )
        payment = Payment.objects.create(
            order=order,
            initiated_by=self.buyer,
            provider=PaymentProvider.SANDBOX,
            method="card",
            status=PaymentStatus.FAILED,
            amount=Decimal("10.00"),
            currency="USD",
            payer_name="Hardening Buyer",
            payer_email=self.buyer.email,
        )
        incident = OperationsIncident(
            title="Paiement cross-tenant",
            category=IncidentCategory.PAYMENT,
            severity=IncidentSeverity.HIGH,
            organization=self.organization,
            payment=payment,
            description="Le paiement ne doit pas traverser les organisations.",
            opened_by=self.staff,
        )
        with self.assertRaises(ValidationError):
            incident.full_clean()

    def test_api_can_explicitly_unassign_incident(self):
        incident = create_incident(
            actor=self.staff,
            title="Incident assigné",
            category=IncidentCategory.SUPPORT,
            severity=IncidentSeverity.LOW,
            organization=self.organization,
            event=self.event,
            description="Test de désassignation.",
            assigned_to=self.staff,
        )
        self.client.force_login(self.staff)
        response = self.client.patch(
            reverse("operations_api:incident-detail", args=[incident.pk]),
            data={"assigned_to": None},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        incident.refresh_from_db()
        self.assertIsNone(incident.assigned_to)
        self.assertIsNone(response.data["assigned_to"])

    def test_published_events_metric_counts_events_not_organizations(self):
        Event.objects.create(
            organizer=self.staff,
            organization=self.organization,
            title="Second Published Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=self.now + timedelta(days=4),
            end_at=self.now + timedelta(days=4, hours=2),
        )
        overview = build_operations_overview(self.staff)
        self.assertEqual(overview["metrics"]["published_events"], 2)
