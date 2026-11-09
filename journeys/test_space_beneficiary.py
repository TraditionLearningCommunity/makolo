"""Journey beneficiary Space and shared mandate access, without a Dossier."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from activities.models import Activity
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
