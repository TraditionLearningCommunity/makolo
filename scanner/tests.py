from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from rest_framework import status
from rest_framework.test import APITestCase

from accounts.models import Role
from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization
from tickets.models import TicketStatus, TicketType
from tickets.services import create_order

from .models import ScanLog, ScanResult, ScannerAssignment
from .services import scan_ticket


User = get_user_model()


class ScannerFixtureMixin:
    password = "Strong-scanner-password-2026!"

    def build_fixture(self):
        self.organizer_role = Role.objects.create(
            name="Organizer",
            code="organizer",
            is_active=True,
        )
        self.scanner_role = Role.objects.create(
            name="Scanner Agent",
            code="scanner-agent",
            is_active=True,
        )

        self.organizer = User.objects.create_user(
            username="scanner-organizer",
            email="scanner-organizer@example.com",
            password=self.password,
        )
        self.organizer.roles.add(self.organizer_role)

        self.agent = User.objects.create_user(
            username="gate-agent",
            email="gate-agent@example.com",
            password=self.password,
        )
        self.agent.roles.add(self.scanner_role)

        self.other_agent = User.objects.create_user(
            username="other-gate-agent",
            email="other-gate-agent@example.com",
            password=self.password,
        )
        self.other_agent.roles.add(self.scanner_role)

        self.participant = User.objects.create_user(
            username="ticket-holder",
            email="ticket-holder@example.com",
            password=self.password,
            first_name="Alice",
            last_name="Participant",
        )
        self.space = Organization.objects.create(
            name="Scanner Fixture Space",
            created_by=self.organizer,
        )

        start_at = timezone.now() + timedelta(hours=2)
        self.event = Event.objects.create(
            organizer=self.organizer,
            organization=self.space,
            title="Makolo Access Day",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start_at,
            end_at=start_at + timedelta(hours=5),
            published_at=timezone.now(),
            capacity=100,
        )
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Standard",
            price=0,
            currency="USD",
            quantity_total=100,
        )
        self.order = create_order(
            buyer=self.participant,
            event=self.event,
            customer_name=self.participant.full_name,
            customer_email=self.participant.email,
            selections=[(self.ticket_type, 1)],
        )
        self.ticket = self.order.tickets.get()
        self.assignment = ScannerAssignment.objects.create(
            event=self.event,
            agent=self.agent,
            assigned_by=self.organizer,
            label="Porte A",
        )

    def make_other_event(self):
        start_at = timezone.now() + timedelta(hours=3)
        return Event.objects.create(
            organizer=self.organizer,
            organization=self.space,
            title="Other Makolo Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start_at,
            end_at=start_at + timedelta(hours=4),
            published_at=timezone.now(),
        )


class ScannerServiceTests(ScannerFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_assigned_agent_can_accept_ticket_once(self):
        outcome = scan_ticket(
            token=self.ticket.qr_token,
            actor=self.agent,
            event=self.event,
            client_reference="scan-1",
        )

        self.ticket.refresh_from_db()
        self.assertTrue(outcome.accepted)
        self.assertEqual(outcome.result, ScanResult.ACCEPTED)
        self.assertEqual(self.ticket.status, TicketStatus.USED)
        self.assertIsNotNone(self.ticket.used_at)
        self.assertEqual(outcome.log.gate, "Porte A")
        self.assertNotEqual(outcome.log.qr_fingerprint, self.ticket.qr_token)
        self.assertEqual(len(outcome.log.qr_fingerprint), 64)

    def test_second_scan_is_rejected_as_duplicate(self):
        first = scan_ticket(
            token=self.ticket.qr_token,
            actor=self.agent,
            event=self.event,
            client_reference="first",
        )
        second = scan_ticket(
            token=self.ticket.qr_token,
            actor=self.agent,
            event=self.event,
            client_reference="second",
        )

        self.assertTrue(first.accepted)
        self.assertFalse(second.accepted)
        self.assertEqual(second.result, ScanResult.DUPLICATE)
        self.assertEqual(
            ScanLog.objects.filter(
                ticket=self.ticket,
                result=ScanResult.ACCEPTED,
            ).count(),
            1,
        )

    def test_same_client_reference_is_idempotent(self):
        first = scan_ticket(
            token=self.ticket.qr_token,
            actor=self.agent,
            event=self.event,
            client_reference="same-request",
        )
        retry = scan_ticket(
            token=self.ticket.qr_token,
            actor=self.agent,
            event=self.event,
            client_reference="same-request",
        )

        self.assertEqual(first.log.pk, retry.log.pk)
        self.assertTrue(retry.accepted)
        self.assertEqual(ScanLog.objects.count(), 1)

    def test_invalid_signature_is_logged_without_raw_token(self):
        raw = "not-a-valid-makolo-token"
        outcome = scan_ticket(
            token=raw,
            actor=self.agent,
            event=self.event,
            client_reference="invalid-1",
        )

        self.assertEqual(outcome.result, ScanResult.INVALID_TOKEN)
        self.assertIsNone(outcome.ticket)
        self.assertNotEqual(outcome.log.qr_fingerprint, raw)
        self.assertNotIn(raw, outcome.log.message)

    def test_ticket_for_another_event_is_rejected(self):
        other_event = self.make_other_event()
        ScannerAssignment.objects.create(
            event=other_event,
            agent=self.agent,
            assigned_by=self.organizer,
            label="Porte B",
        )

        outcome = scan_ticket(
            token=self.ticket.qr_token,
            actor=self.agent,
            event=other_event,
            client_reference="wrong-event",
        )

        self.ticket.refresh_from_db()
        self.assertEqual(outcome.result, ScanResult.WRONG_EVENT)
        self.assertEqual(self.ticket.status, TicketStatus.VALID)

    def test_unassigned_scanner_agent_cannot_scan_event(self):
        with self.assertRaises(PermissionDenied):
            scan_ticket(
                token=self.ticket.qr_token,
                actor=self.other_agent,
                event=self.event,
                client_reference="unauthorized",
            )

        self.assertFalse(ScanLog.objects.filter(scanner=self.other_agent).exists())

    def test_cancelled_ticket_is_rejected(self):
        self.ticket.status = TicketStatus.CANCELLED
        self.ticket.cancelled_at = timezone.now()
        self.ticket.save(update_fields=["status", "cancelled_at", "updated_at"])

        outcome = scan_ticket(
            token=self.ticket.qr_token,
            actor=self.agent,
            event=self.event,
            client_reference="cancelled",
        )

        self.assertEqual(outcome.result, ScanResult.INVALID_STATUS)
        self.assertFalse(outcome.accepted)


class ScannerApiTests(ScannerFixtureMixin, APITestCase):
    def setUp(self):
        self.build_fixture()

    def test_assigned_agent_can_scan_through_api(self):
        self.client.force_authenticate(self.agent)
        response = self.client.post(
            "/api/v1/scanner/scan/",
            {
                "event_id": str(self.event.pk),
                "token": self.ticket.qr_token,
                "client_reference": "api-scan-1",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["accepted"])
        self.assertEqual(response.data["result"], ScanResult.ACCEPTED)

    def test_regular_participant_cannot_scan(self):
        self.client.force_authenticate(self.participant)
        response = self.client.post(
            "/api/v1/scanner/scan/",
            {
                "event_id": str(self.event.pk),
                "token": self.ticket.qr_token,
                "client_reference": "forbidden",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_scanner_only_sees_own_logs(self):
        scan_ticket(
            token=self.ticket.qr_token,
            actor=self.agent,
            event=self.event,
            client_reference="visible-log",
        )
        self.client.force_authenticate(self.other_agent)

        response = self.client.get("/api/v1/scanner/logs/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)

    def test_organizer_can_create_assignment_for_scanner_role(self):
        self.client.force_authenticate(self.organizer)
        response = self.client.post(
            "/api/v1/scanner/assignments/",
            {
                "event_id": str(self.event.pk),
                "agent_id": str(self.other_agent.pk),
                "label": "Porte VIP",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            ScannerAssignment.objects.filter(
                event=self.event,
                agent=self.other_agent,
                label="Porte VIP",
            ).exists()
        )

    def test_assignment_rejects_user_without_scanner_role(self):
        self.client.force_authenticate(self.organizer)
        response = self.client.post(
            "/api/v1/scanner/assignments/",
            {
                "event_id": str(self.event.pk),
                "agent_id": str(self.participant.pk),
                "label": "Porte C",
                "is_active": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ScannerWebTests(ScannerFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_scanner_home_requires_authentication(self):
        response = self.client.get(reverse("scanner:home"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:login"), response.url)

    def test_assigned_agent_can_open_event_console(self):
        self.client.force_login(self.agent)

        response = self.client.get(reverse("scanner:console", args=[self.event.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.event.title)
        self.assertContains(response, "Démarrer la caméra")

    def test_regular_user_cannot_open_event_console(self):
        self.client.force_login(self.participant)

        response = self.client.get(reverse("scanner:console", args=[self.event.slug]))

        self.assertEqual(response.status_code, 404)

    def test_web_scan_endpoint_consumes_ticket(self):
        self.client.force_login(self.agent)

        response = self.client.post(
            reverse("scanner:scan", args=[self.event.slug]),
            {
                "token": self.ticket.qr_token,
                "client_reference": "web-scan-1",
            },
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["accepted"])
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, TicketStatus.USED)

    def test_organizer_can_open_assignment_management(self):
        self.client.force_login(self.organizer)

        response = self.client.get(reverse("scanner:assignments"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Agents scanner")
