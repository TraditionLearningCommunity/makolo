from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from notifications.models import DeliveryChannel, DeliveryStatus, Notification, NotificationDelivery

from .models import (
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
    OperationsIncident,
    WorkerHeartbeat,
    WorkerState,
)
from .product_overview import DEMO_SEED, build_product_operations_overview


User = get_user_model()


class DemoSafeOperationsOverviewTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="demo-safe-ops",
            email="demo-safe-ops@example.com",
            password="Strong-demo-safe-ops-2026!",
            is_staff=True,
        )

    def test_demo_incident_worker_and_notification_backlog_are_not_operational_alerts(self):
        now = timezone.now()
        OperationsIncident.objects.create(
            title="Incident critique de démonstration",
            category=IncidentCategory.NOTIFICATION,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.OPEN,
            description="Scénario seedé.",
            opened_by=self.staff,
            metadata={"seed": DEMO_SEED},
        )
        WorkerHeartbeat.objects.create(
            worker_name="demo-worker",
            instance_id="demo-instance",
            state=WorkerState.DEGRADED,
            last_seen_at=now - timedelta(minutes=30),
            metadata={"seed": DEMO_SEED},
        )
        notification = Notification.objects.create(
            recipient=self.staff,
            title="Démo",
            message="Notification seedée",
            metadata={"seed": DEMO_SEED},
        )
        NotificationDelivery.objects.create(
            notification=notification,
            channel=DeliveryChannel.EMAIL,
            destination=self.staff.email,
            status=DeliveryStatus.QUEUED,
            scheduled_for=now - timedelta(hours=2),
        )

        overview = build_product_operations_overview(self.staff)

        self.assertTrue(overview["demo_data_present"])
        self.assertEqual(overview["metrics"]["open_incidents"], 0)
        self.assertEqual(overview["metrics"]["critical_incidents"], 0)
        self.assertEqual(overview["metrics"]["stale_workers"], 0)
        self.assertEqual(overview["metrics"]["overdue_deliveries"], 0)
        self.assertFalse(any(row["code"] == "critical_incidents" for row in overview["signals"]))
        self.assertFalse(any(row["code"] == "notification_backlog" for row in overview["signals"]))
        self.assertFalse(any(row["code"] == "stale_workers" for row in overview["signals"]))

    def test_real_operational_records_still_surface_next_to_demo_data(self):
        OperationsIncident.objects.create(
            title="Incident réel",
            category=IncidentCategory.SECURITY,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.OPEN,
            description="Incident non seedé.",
            opened_by=self.staff,
        )
        OperationsIncident.objects.create(
            title="Incident démo",
            category=IncidentCategory.SECURITY,
            severity=IncidentSeverity.CRITICAL,
            status=IncidentStatus.OPEN,
            description="Incident seedé.",
            opened_by=self.staff,
            metadata={"seed": DEMO_SEED},
        )

        overview = build_product_operations_overview(self.staff)

        self.assertEqual(overview["metrics"]["open_incidents"], 1)
        self.assertEqual(overview["metrics"]["critical_incidents"], 1)
        self.assertEqual(overview["health"], "critical")
        self.assertEqual(
            next(row["count"] for row in overview["signals"] if row["code"] == "critical_incidents"),
            1,
        )

    def test_operations_dashboard_explicitly_labels_demo_presence(self):
        WorkerHeartbeat.objects.create(
            worker_name="demo-worker",
            instance_id="demo-instance",
            state=WorkerState.STOPPED,
            metadata={"seed": DEMO_SEED},
        )
        self.client.force_login(self.staff)

        response = self.client.get(reverse("operations:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Données de démonstration détectées")
        self.assertContains(response, "excluent les enregistrements marqués")
