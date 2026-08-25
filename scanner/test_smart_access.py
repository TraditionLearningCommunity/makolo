from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase

from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from tickets.models import TicketStatus

from .intelligence import event_access_snapshot
from .models import EventAccessGate, ScanLog, ScanResult, ScannerAssignment
from .services import scan_ticket
from .tests import ScannerFixtureMixin


class SmartAccessServiceTests(ScannerFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()
        grant_space_role(
            profile=self.organizer,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
        )
        self.gate = EventAccessGate.objects.create(
            event=self.event,
            name="Entrée Nord",
            throughput_target_per_minute=10,
            warning_rejection_rate=30,
            created_by=self.organizer,
        )
        self.assignment.access_gate = self.gate
        self.assignment.save(update_fields=["access_gate", "updated_at"])

    def test_assignment_uses_configured_gate_automatically(self):
        outcome = scan_ticket(
            token=self.ticket.qr_token,
            actor=self.agent,
            event=self.event,
            client_reference="smart-gate-1",
        )

        self.assertTrue(outcome.accepted)
        self.assertEqual(outcome.log.access_gate, self.gate)
        self.assertEqual(outcome.log.gate, "Entrée Nord")

    def test_paused_gate_rejects_before_ticket_consumption(self):
        self.gate.is_active = False
        self.gate.save(update_fields=["is_active", "updated_at"])

        outcome = scan_ticket(
            token=self.ticket.qr_token,
            actor=self.agent,
            event=self.event,
            client_reference="paused-gate",
        )

        self.ticket.refresh_from_db()
        self.assertFalse(outcome.accepted)
        self.assertEqual(outcome.result, ScanResult.GATE_UNAVAILABLE)
        self.assertEqual(self.ticket.status, TicketStatus.VALID)

    def test_assignment_rejects_gate_from_another_event(self):
        other_event = self.make_other_event()
        other_gate = EventAccessGate.objects.create(event=other_event, name="Autre porte")
        assignment = ScannerAssignment(
            event=self.event,
            agent=self.other_agent,
            assigned_by=self.organizer,
            access_gate=other_gate,
            label="Mauvaise porte",
        )

        with self.assertRaises(ValidationError):
            assignment.full_clean()

    def test_live_snapshot_detects_recent_invalid_qr_spike_without_pii(self):
        for index in range(5):
            ScanLog.objects.create(
                event=self.event,
                scanner=self.agent,
                assignment=self.assignment,
                access_gate=self.gate,
                result=ScanResult.INVALID_TOKEN,
                message="QR invalide",
                client_reference=f"invalid-{index}",
                gate=self.gate.name,
            )

        snapshot = event_access_snapshot(self.event)

        self.assertEqual(snapshot["windows"]["last_15"]["invalid_qr"], 5)
        kinds = {incident["kind"] for incident in snapshot["incidents"]}
        self.assertIn("invalid_qr_spike", kinds)
        self.assertIn("high_rejection_rate", kinds)
        self.assertNotIn(self.participant.email, str(snapshot))
        self.assertNotIn(self.participant.full_name, str(snapshot))


class SmartAccessApiTests(ScannerFixtureMixin, APITestCase):
    def setUp(self):
        self.build_fixture()
        grant_space_role(
            profile=self.organizer,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
        )
        self.gate = EventAccessGate.objects.create(
            event=self.event,
            name="Porte VIP",
            throughput_target_per_minute=12,
            created_by=self.organizer,
        )
        self.assignment.access_gate = self.gate
        self.assignment.save(update_fields=["access_gate", "updated_at"])

    def test_assigned_agent_can_read_live_snapshot(self):
        self.client.force_authenticate(self.agent)

        response = self.client.get(f"/api/v1/scanner/events/{self.event.slug}/live/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["event"]["slug"], self.event.slug)
        self.assertEqual(response.data["gates"][0]["name"], "Porte VIP")
        self.assertNotIn("holder_email", str(response.data))

    def test_scan_api_accepts_first_class_gate(self):
        self.client.force_authenticate(self.agent)

        response = self.client.post(
            "/api/v1/scanner/scan/",
            {
                "event_id": str(self.event.pk),
                "access_gate_id": str(self.gate.pk),
                "token": self.ticket.qr_token,
                "client_reference": "api-gate-scan",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["accepted"])
        self.assertEqual(response.data["scan"]["access_gate"]["id"], str(self.gate.pk))

    def test_organizer_can_create_gate_but_participant_cannot(self):
        self.client.force_authenticate(self.organizer)
        response = self.client.post(
            "/api/v1/scanner/gates/",
            {
                "event_id": str(self.event.pk),
                "name": "Porte Sud",
                "throughput_target_per_minute": 15,
                "warning_rejection_rate": 25,
                "priority": 20,
                "is_active": True,
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(self.participant)
        forbidden = self.client.post(
            "/api/v1/scanner/gates/",
            {
                "event_id": str(self.event.pk),
                "name": "Porte interdite",
            },
            format="json",
        )
        self.assertEqual(forbidden.status_code, status.HTTP_400_BAD_REQUEST)


class SmartAccessWebTests(ScannerFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()
        grant_space_role(
            profile=self.organizer,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
        )
        self.gate = EventAccessGate.objects.create(
            event=self.event,
            name="Entrée principale",
            created_by=self.organizer,
        )
        self.assignment.access_gate = self.gate
        self.assignment.save(update_fields=["access_gate", "updated_at"])

    def test_assigned_agent_can_open_live_access_dashboard(self):
        self.client.force_login(self.agent)

        response = self.client.get(reverse("scanner:live-access", args=[self.event.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Smart Access Live")
        self.assertContains(response, "Entrée principale")

    def test_organizer_can_open_gate_management(self):
        self.client.force_login(self.organizer)

        response = self.client.get(reverse("scanner:gates"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Portes d’accès")
        self.assertContains(response, "Entrée principale")
