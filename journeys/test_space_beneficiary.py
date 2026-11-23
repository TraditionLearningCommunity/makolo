"""Journey beneficiary Space and shared mandate access, without a Dossier."""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse
from rest_framework.test import APIClient

from activities.models import Activity, Occurrence
from authorization.constants import SystemRoleCode
from authorization.services import grant_space_role, revoke_mandate
from organizations.models import Organization

from .collaboration_services import can_access_case
from .models import Journey
from .services import create_journey
from .models import WorkflowKind


User = get_user_model()


class SpaceBeneficiaryJourneyTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="space-journey-owner", email="space-journey-owner@example.com",
        )
        self.member = User.objects.create_user(
            username="space-journey-member", email="space-journey-member@example.com",
        )
        self.outsider = User.objects.create_user(
            username="space-journey-outsider", email="space-journey-outsider@example.com",
        )
        self.provider = User.objects.create_user(
            username="space-journey-provider", email="space-journey-provider@example.com",
        )
        self.space = Organization.objects.create(
            name="Client institutionnel", created_by=self.owner,
        )
        self.activity = Activity.objects.create(
            owner_profile=self.provider, created_by=self.provider,
            title="Prestation institutionnelle",
        )
        self.owner_mandate = grant_space_role(
            profile=self.owner, space=self.space, role=SystemRoleCode.SPACE_OWNER,
        )
        self.member_mandate = grant_space_role(
            profile=self.member, space=self.space, role=SystemRoleCode.ACTIVITY_MANAGER,
        )

    def _create(self, **kwargs):
        return create_journey(
            initiated_by=self.owner,
            beneficiary_space=self.space,
            activity=self.activity,
            workflow=WorkflowKind.SERVICE,
            **kwargs,
        )

    def test_one_journey_shared_by_mandated_space_members(self):
        journey = self._create()
        self.assertEqual(journey.beneficiary_space_id, self.space.pk)
        self.assertIsNone(journey.beneficiary_id)
        self.assertIsNone(journey.external_beneficiary_id)
        self.assertEqual(journey.beneficiary_display_name, self.space.name)
        self.assertEqual(Journey.objects.count(), 1)
        self.assertTrue(can_access_case(self.owner, journey))
        self.assertTrue(can_access_case(self.member, journey))
        self.assertFalse(can_access_case(self.member, journey, write=True))
        self.assertFalse(can_access_case(self.member, journey, restricted=True))
        self.assertFalse(can_access_case(self.outsider, journey))

    def test_membership_authority_is_revalidated_after_revocation(self):
        journey = self._create()
        self.assertTrue(can_access_case(self.member, journey))
        revoke_mandate(mandate=self.member_mandate, actor=self.owner)
        self.assertFalse(can_access_case(self.member, journey))

    def test_space_creation_requires_a_current_mandate(self):
        with self.assertRaises(PermissionDenied):
            create_journey(
                initiated_by=self.outsider,
                beneficiary_space=self.space,
                activity=self.activity,
                workflow=WorkflowKind.SERVICE,
            )

    def test_beneficiary_kinds_remain_mutually_exclusive(self):
        with self.assertRaises(ValidationError):
            self._create(beneficiary=self.owner)

    def test_canonical_day_of_shared_between_members_without_dossier(self):
        occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(minutes=20),
            end_at=timezone.now() + timedelta(hours=2),
        )
        journey = self._create(occurrence=occurrence)
        url = f"/api/v1/operations/occurrences/{occurrence.pk}/experience/day-of/"
        client = APIClient()

        client.force_authenticate(user=self.member)
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        institutional = response.data["data"]["sections"]["institutional"]
        self.assertEqual([item["id"] for item in institutional], [str(journey.pk)])
        self.assertEqual(institutional[0]["beneficiary"]["id"], str(self.space.pk))
        self.assertNotIn("participant", response.data["data"]["sections"])
        self.assertEqual(Journey.objects.filter(pk=journey.pk).count(), 1)

        client.force_authenticate(user=self.outsider)
        self.assertEqual(client.get(url).status_code, 404)

        client.force_authenticate(user=self.member)
        revoke_mandate(mandate=self.member_mandate, actor=self.owner)
        self.assertEqual(client.get(url).status_code, 404)

    def test_space_beneficiary_can_use_web_day_of_for_external_provider(self):
        occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() - timedelta(minutes=5),
            end_at=timezone.now() + timedelta(hours=2),
        )
        journey = self._create(occurrence=occurrence)
        self.assertEqual(journey.beneficiary_space_id, self.space.pk)
        url = reverse(
            "organizations:space-occurrence-day-of",
            kwargs={"slug": self.space.slug, "occurrence_id": occurrence.pk},
        )
        self.client.force_login(self.owner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Démarches de l'Espace")
        self.assertContains(response, self.space.name)

    def test_selected_space_cannot_read_another_spaces_institutional_journey(self):
        occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() - timedelta(minutes=5),
            end_at=timezone.now() + timedelta(hours=2),
        )
        self._create(occurrence=occurrence)
        unrelated_space = Organization.objects.create(
            name="Autre client", created_by=self.member,
        )
        grant_space_role(
            profile=self.member, space=unrelated_space,
            role=SystemRoleCode.SPACE_OWNER,
        )
        url = (
            f"/api/v1/operations/occurrences/{occurrence.pk}/experience/day-of/"
            f"?actor_space={unrelated_space.pk}"
        )
        client = APIClient()
        client.force_authenticate(user=self.member)
        response = client.get(url)
        self.assertEqual(response.status_code, 404)
