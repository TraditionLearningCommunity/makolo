from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from automation.models import AutomationRun, AutomationRunStatus
from events.models import Event, EventStatus, EventVisibility
from events.selectors import get_events_visible_to
from notifications.models import DeliveryChannel, DeliveryStatus, Notification, NotificationDelivery
from organizations.models import Organization, OrganizationVerificationStatus
from payments.models import Payment, PaymentEvent, PaymentProvider, PaymentStatus
from scanner.models import ScanLog, ScanResult
from tickets.models import TicketOrder, TicketOrderStatus

from .models import (
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
    ModerationCase,
    OperationsAuditLog,
    OperationsIncident,
    WorkerHeartbeat,
    WorkerState,
)
from .services import (
    build_operations_overview,
    change_organization_verification,
    create_incident,
    moderate_event,
    record_worker_heartbeat,
    update_incident,
)


User = get_user_model()


class OperationsCenterTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.staff = User.objects.create_user(
            username="ops-staff",
            email="ops-staff@test.local",
            password="Strong-password-2026!",
            is_staff=True,
        )
        self.regular = User.objects.create_user(
            username="ops-regular",
            email="ops-regular@test.local",
            password="Strong-password-2026!",
        )
        self.buyer = User.objects.create_user(
            username="ops-buyer",
            email="private-buyer@test.local",
            password="Strong-password-2026!",
        )
        self.organization = Organization.objects.create(
            name="Makolo Operations Test",
            verification_status=OrganizationVerificationStatus.PENDING,
            created_by=self.staff,
        )
        self.event = Event.objects.create(
            organizer=self.staff,
            organization=self.organization,
            title="Operations Live Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=self.now + timedelta(days=2),
            end_at=self.now + timedelta(days=2, hours=4),
        )
        self.order = TicketOrder.objects.create(
            event=self.event,
            buyer=self.buyer,
            customer_name="Private Buyer",
            customer_email=self.buyer.email,
            status=TicketOrderStatus.PENDING,
            total_amount=Decimal("25.00"),
            currency="USD",
            expires_at=self.now + timedelta(minutes=20),
        )

    def test_operations_web_is_staff_only(self):
        self.client.force_login(self.regular)
        response = self.client.get(reverse("operations:dashboard"))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.staff)
        response = self.client.get(reverse("operations:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Makolo Operations Center")

    def test_operations_api_is_staff_only(self):
        self.client.force_login(self.regular)
        response = self.client.get(reverse("operations_api:overview"))
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.staff)
        response = self.client.get(reverse("operations_api:overview"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("metrics", response.data)

    def test_organization_suspension_is_audited_and_hides_public_events(self):
        change_organization_verification(
            organization=self.organization,
            status=OrganizationVerificationStatus.SUSPENDED,
            actor=self.staff,
            reason="Contrôle de conformité test.",
        )
        self.organization.refresh_from_db()
        self.assertEqual(self.organization.verification_status, OrganizationVerificationStatus.SUSPENDED)
        self.assertTrue(ModerationCase.objects.filter(organization=self.organization, status="actioned").exists())
        self.assertTrue(OperationsAuditLog.objects.filter(action="organization.verification_changed").exists())
        self.assertFalse(get_events_visible_to(AnonymousUser()).filter(pk=self.event.pk).exists())

    def test_event_moderation_is_explicit_and_audited(self):
        moderate_event(
            event=self.event,
            action="unlist",
            actor=self.staff,
            reason="Signalement de contenu test.",
        )
        self.event.refresh_from_db()
        self.assertEqual(self.event.visibility, EventVisibility.UNLISTED)
        self.assertTrue(ModerationCase.objects.filter(event=self.event, status="actioned").exists())
        self.assertTrue(OperationsAuditLog.objects.filter(action="event.moderation.unlist").exists())

    def test_event_cancellation_records_timestamp(self):
        moderate_event(
            event=self.event,
            action="cancel",
            actor=self.staff,
            reason="Incident sécurité test.",
        )
        self.event.refresh_from_db()
        self.assertEqual(self.event.status, EventStatus.CANCELLED)
        self.assertIsNotNone(self.event.cancelled_at)

    def test_incident_lifecycle_tracks_acknowledgement_and_resolution(self):
        incident = create_incident(
            actor=self.staff,
            title="Webhook PSP bloqué",
            category=IncidentCategory.PAYMENT,
            severity=IncidentSeverity.HIGH,
            organization=self.organization,
            event=self.event,
            description="Investigation requise.",
        )
        incident = update_incident(
            incident=incident,
            actor=self.staff,
            status=IncidentStatus.INVESTIGATING,
            assigned_to=self.staff,
        )
        self.assertIsNotNone(incident.acknowledged_at)
        incident = update_incident(
            incident=incident,
            actor=self.staff,
            status=IncidentStatus.RESOLVED,
            resolution="Webhook retraité et idempotence vérifiée.",
        )
        self.assertIsNotNone(incident.resolved_at)
        self.assertEqual(incident.status, IncidentStatus.RESOLVED)
        self.assertGreaterEqual(OperationsAuditLog.objects.filter(target_id=str(incident.pk)).count(), 3)

    def test_resolved_incident_requires_resolution(self):
        incident = create_incident(
            actor=self.staff,
            title="Incident sans résolution",
            category=IncidentCategory.OTHER,
            severity=IncidentSeverity.MEDIUM,
            description="Test.",
        )
        with self.assertRaises(ValidationError):
            update_incident(
                incident=incident,
                actor=self.staff,
                status=IncidentStatus.RESOLVED,
                resolution="",
            )

    def test_incident_cannot_be_assigned_to_non_staff(self):
        incident = OperationsIncident(
            title="Assignation invalide",
            category=IncidentCategory.SUPPORT,
            severity=IncidentSeverity.LOW,
            description="Test.",
            opened_by=self.staff,
            assigned_to=self.regular,
        )
        with self.assertRaises(ValidationError):
            incident.full_clean()

    def test_worker_heartbeat_detects_stale_worker(self):
        heartbeat = record_worker_heartbeat(
            worker_name="autopilot",
            instance_id="test-worker",
            state=WorkerState.HEALTHY,
            cycle_finished=True,
        )
        WorkerHeartbeat.objects.filter(pk=heartbeat.pk).update(last_seen_at=self.now - timedelta(minutes=3))
        overview = build_operations_overview(self.staff)
        self.assertEqual(overview["metrics"]["stale_workers"], 1)
        self.assertEqual(overview["health"], "critical")
        self.assertTrue(any(row["code"] == "stale_workers" for row in overview["signals"]))

    def test_invalid_webhook_creates_critical_signal_without_payload_exposure(self):
        PaymentEvent.objects.create(
            provider=PaymentProvider.SANDBOX,
            event_id="evt-invalid-signature",
            event_type="payment.updated",
            signature_valid=False,
            processed=False,
            payload_hash="a" * 64,
            payload={"payer_email": self.buyer.email, "secret": "never-surface-me"},
        )
        self.client.force_login(self.staff)
        response = self.client.get(reverse("operations_api:overview"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["metrics"]["invalid_webhooks_24h"], 1)
        body = response.content.decode()
        self.assertNotIn(self.buyer.email, body)
        self.assertNotIn("never-surface-me", body)
        self.assertTrue(any(row["code"] == "invalid_webhooks" for row in response.data["signals"]))

    def test_payment_failure_rate_signal_uses_aggregate_counts(self):
        for index in range(5):
            Payment.objects.create(
                order=self.order,
                initiated_by=self.buyer,
                provider=PaymentProvider.SANDBOX,
                method="card",
                status=PaymentStatus.FAILED,
                amount=Decimal("25.00"),
                currency="USD",
                payer_name="Private Buyer",
                payer_email=self.buyer.email,
                failure_code=f"TEST-{index}",
            )
        overview = build_operations_overview(self.staff)
        self.assertEqual(overview["metrics"]["payment_failure_rate_24h"], 100.0)
        self.assertTrue(any(row["code"] == "payment_failure_rate" for row in overview["signals"]))

    def test_scan_anomaly_signal_is_aggregate(self):
        for index in range(10):
            ScanLog.objects.create(
                event=self.event,
                scanner=self.staff,
                result=ScanResult.INVALID_TOKEN if index < 5 else ScanResult.ACCEPTED,
                message="Test scan",
                qr_fingerprint=f"{index:064x}",
            )
        overview = build_operations_overview(self.staff)
        self.assertEqual(overview["metrics"]["scans_15m"], 10)
        self.assertEqual(overview["metrics"]["invalid_scans_15m"], 5)
        self.assertTrue(any(row["code"] == "scan_rejection_rate" for row in overview["signals"]))
        self.assertTrue(any(row["code"] == "invalid_scans" for row in overview["signals"]))

    def test_automation_and_notification_failures_surface(self):
        AutomationRun.objects.create(
            event=self.event,
            rule_key="test_failure",
            dedup_key="ops-test-failure",
            status=AutomationRunStatus.FAILED,
            error="Synthetic failure",
        )
        notification = Notification.objects.create(
            recipient=self.buyer,
            title="Test delivery",
            message="Test",
        )
        NotificationDelivery.objects.create(
            notification=notification,
            channel=DeliveryChannel.EMAIL,
            destination=self.buyer.email,
            status=DeliveryStatus.FAILED,
            last_error="Synthetic failure",
        )
        overview = build_operations_overview(self.staff)
        self.assertEqual(overview["metrics"]["automation_failures_24h"], 1)
        self.assertEqual(overview["metrics"]["failed_deliveries_24h"], 1)
        self.assertTrue(any(row["code"] == "automation_failures" for row in overview["signals"]))
        self.assertTrue(any(row["code"] == "notification_failures" for row in overview["signals"]))

    def test_incident_api_create_and_patch_are_audited(self):
        self.client.force_login(self.staff)
        create_response = self.client.post(
            reverse("operations_api:incidents"),
            data={
                "title": "Incident API",
                "category": IncidentCategory.ACCESS,
                "severity": IncidentSeverity.HIGH,
                "organization": str(self.organization.pk),
                "event": str(self.event.pk),
                "description": "Créé par API.",
            },
            content_type="application/json",
        )
        self.assertEqual(create_response.status_code, 201)
        incident_id = create_response.data["id"]
        patch_response = self.client.patch(
            reverse("operations_api:incident-detail", args=[incident_id]),
            data={"status": IncidentStatus.RESOLVED, "resolution": "Résolu via API."},
            content_type="application/json",
        )
        self.assertEqual(patch_response.status_code, 200)
        self.assertEqual(patch_response.data["status"], IncidentStatus.RESOLVED)
        self.assertTrue(OperationsAuditLog.objects.filter(target_id=str(incident_id), action="incident.updated").exists())
