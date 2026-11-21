"""Real domain action -> Domain Event -> Notifications regression contracts.

These fixtures use the owner services instead of fabricating demo notifications.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from access.services import issue_access, revoke_access
from activities.models import Activity
from journeys.models import Journey, JourneyStatus, WorkflowKind
from journeys.services import (
    cancel_journey,
    create_request,
    expire_journey,
    reject_request,
)
from notifications.models import Notification


User = get_user_model()


class RealLifecycleNotificationTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_superuser(
            username="real-notification-operator",
            email="operator-notify@example.com",
            password="Test-only-2026-operator!",
        )
        self.participant = User.objects.create_user(
            username="real-notification-participant",
            email="participant-notify@example.com",
            password="Test-only-2026-participant!",
        )
        self.activity = Activity.objects.create(
            owner_profile=self.operator,
            created_by=self.operator,
            title="Atelier Makolo",
        )
        self.journey = Journey.objects.create(
            initiated_by=self.participant,
            beneficiary=self.participant,
            activity=self.activity,
            workflow=WorkflowKind.RESERVATION,
            status=JourneyStatus.SUBMITTED,
        )

    def test_cancelled_journey_notifies_only_beneficiary_once(self):
        with self.captureOnCommitCallbacks(execute=True):
            cancel_journey(journey=self.journey, actor=self.participant)

        notifications = Notification.objects.filter(
            template_key="journey.cancelled",
        )
        self.assertEqual(notifications.count(), 1)
        alert = notifications.get()
        self.assertEqual(alert.recipient_id, self.participant.pk)
        self.assertEqual(alert.journey_id, self.journey.pk)
        self.assertEqual(alert.activity_id, self.activity.pk)
        self.assertEqual(alert.metadata["journey_id"], str(self.journey.pk))

        with self.captureOnCommitCallbacks(execute=True):
            cancel_journey(journey=self.journey, actor=self.participant)
        self.assertEqual(notifications.count(), 1)

        self.client.force_login(self.operator)
        response = self.client.get("/api/v1/notifications/")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(any(
            row["id"] == str(alert.pk) for row in response.json()["results"]
        ))

    def test_expired_journey_notifies_beneficiary_after_real_transition(self):
        self.journey.expires_at = timezone.now() - timedelta(minutes=1)
        self.journey.save(update_fields=["expires_at"])
        with self.captureOnCommitCallbacks(execute=True):
            expire_journey(journey=self.journey)

        alert = Notification.objects.get(template_key="journey.expired")
        self.assertEqual(alert.recipient_id, self.participant.pk)
        self.assertEqual(alert.journey_id, self.journey.pk)

    def test_rejected_request_notifies_requester_without_duplicate_rejection(self):
        request = create_request(
            journey=self.journey,
            requester=self.participant,
        )
        with self.captureOnCommitCallbacks(execute=True):
            reject_request(request=request, actor=self.operator)

        alerts = Notification.objects.filter(recipient=self.participant)
        self.assertEqual(
            alerts.filter(template_key="journey.request.rejected").count(),
            1,
        )
        self.assertEqual(
            alerts.filter(template_key="journey.rejected").count(), 0,
        )
        alert = alerts.get(template_key="journey.request.rejected")
        self.assertEqual(alert.metadata["request_id"], str(request.pk))
        self.assertEqual(alert.journey_id, self.journey.pk)

    def test_revoked_access_notifies_beneficiary_and_keeps_history(self):
        with self.captureOnCommitCallbacks(execute=True):
            access = issue_access(
                beneficiary=self.participant,
                activity=self.activity,
                occurrence=None,
                journey=self.journey,
                source_key="real-notifications-test",
            )
        with self.captureOnCommitCallbacks(execute=True):
            revoke_access(access=access, actor=self.operator)

        alert = Notification.objects.get(template_key="access.revoked")
        self.assertEqual(alert.recipient_id, self.participant.pk)
        self.assertEqual(alert.access_id, access.pk)
        self.assertEqual(alert.activity_id, self.activity.pk)

        with self.captureOnCommitCallbacks(execute=True):
            revoke_access(access=access, actor=self.operator)
        self.assertEqual(
            Notification.objects.filter(template_key="access.revoked").count(),
            1,
        )

    def test_demo_origin_is_distinct_from_real_notification(self):
        with self.captureOnCommitCallbacks(execute=True):
            cancel_journey(journey=self.journey, actor=self.participant)
        demo = Notification.objects.create(
            recipient=self.participant,
            title="Exemple de démonstration",
            message="Exemple de recette",
            metadata={"seed": "makolo-demo"},
        )
        self.client.force_login(self.participant)
        response = self.client.get("/api/v1/notifications/")
        self.assertEqual(response.status_code, 200)
        rows = {row["id"]: row for row in response.json()["results"]}
        self.assertTrue(rows[str(demo.pk)]["is_demo"])
        real = Notification.objects.get(template_key="journey.cancelled")
        self.assertFalse(rows[str(real.pk)]["is_demo"])
