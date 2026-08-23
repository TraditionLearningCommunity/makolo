from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.manual_grants import grant_access_manually
from access.services import issue_access
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role
from organizations.models import Organization


User = get_user_model()


class ManualAccessAttributionTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username="attribution-creator",
            email="attribution-creator@example.com",
        )
        self.actor = User.objects.create_user(
            username="attribution-actor",
            email="attribution-actor@example.com",
            first_name="Naomi",
            last_name="Kabongo",
        )
        self.beneficiary = User.objects.create_user(
            username="attribution-beneficiary",
            email="attribution-beneficiary@example.com",
            password="Attribution-2026!",
        )
        self.space = Organization.objects.create(
            name="Copperbelt Sports",
            created_by=self.creator,
        )
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.creator,
            title="Accès attribué",
            status=ActivityStatus.PUBLISHED,
        )
        self.self_activity = Activity.objects.create(
            space=self.space,
            created_by=self.creator,
            title="Accès auto-émis",
            status=ActivityStatus.PUBLISHED,
        )
        now = timezone.now()
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=now + timedelta(days=2),
            end_at=now + timedelta(days=2, hours=1),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.self_occurrence = Occurrence.objects.create(
            activity=self.self_activity,
            start_at=now + timedelta(days=3),
            end_at=now + timedelta(days=3, hours=1),
            status=OccurrenceStatus.SCHEDULED,
        )
        grant_space_role(
            profile=self.actor,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
        )

    def test_manual_access_detail_shows_human_issuer_but_not_internal_reason(self):
        access = grant_access_manually(
            actor=self.actor,
            beneficiary=self.beneficiary,
            activity=self.activity,
            occurrence=self.occurrence,
            reason="Accès presse interne",
        )
        self.client.force_login(self.beneficiary)
        response = self.client.get(
            reverse("core:participant-access-detail", kwargs={"pk": access.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Autorisé par Naomi Kabongo")
        self.assertContains(response, "Accordé le")
        self.assertNotContains(response, "Accès presse interne")

    def test_self_issued_access_does_not_claim_human_authorization(self):
        access = issue_access(
            beneficiary=self.beneficiary,
            activity=self.self_activity,
            occurrence=self.self_occurrence,
            issued_by=self.beneficiary,
        )
        self.client.force_login(self.beneficiary)
        response = self.client.get(
            reverse("core:participant-access-detail", kwargs={"pk": access.pk})
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Autorisé par")
