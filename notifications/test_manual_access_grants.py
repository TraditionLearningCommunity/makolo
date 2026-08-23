from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.manual_grants import grant_access_manually
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from organizations.models import Organization

from .models import Notification


User = get_user_model()


class ManualAccessGrantNotificationTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username="notify-manual-creator",
            email="notify-manual-creator@example.com",
        )
        self.actor = User.objects.create_user(
            username="notify-manual-actor",
            email="notify-manual-actor@example.com",
            first_name="Naomi",
            last_name="Kabongo",
        )
        self.beneficiary = User.objects.create_user(
            username="notify-manual-beneficiary",
            email="notify-manual-beneficiary@example.com",
        )
        self.other = User.objects.create_user(
            username="notify-manual-other",
            email="notify-manual-other@example.com",
        )
        self.space = Organization.objects.create(
            name="Notifications manuelles",
            created_by=self.creator,
        )
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.creator,
            title="Atelier presse",
            status=ActivityStatus.PUBLISHED,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=1),
            status=OccurrenceStatus.SCHEDULED,
        )
        grant_space_role(
            profile=self.actor,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
        )

    def test_manual_grant_emits_exactly_one_beneficiary_notification_without_internal_reason(self):
        with self.captureOnCommitCallbacks(execute=True):
            access = grant_access_manually(
                actor=self.actor,
                beneficiary=self.beneficiary,
                activity=self.activity,
                occurrence=self.occurrence,
                reason="Presse - note interne confidentielle",
            )

        notifications = Notification.objects.filter(recipient=self.beneficiary)
        self.assertEqual(notifications.count(), 1)
        notification = notifications.get()
        self.assertEqual(
            notification.action_url,
            reverse("core:participant-access-detail", kwargs={"pk": access.pk}),
        )
        self.assertNotIn("note interne", notification.message.lower())
        self.assertFalse(Notification.objects.filter(recipient=self.other).exists())
