from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.models import Mandate
from authorization.services import grant_space_role
from journeys.collaboration_services import can_access_case
from journeys.models import ExternalBeneficiary, Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization, Team, TeamMembership

from .models import Dossier, DossierAssignment, DossierAssignmentStatus, DossierJourneyLink
from .selectors import visible_linked_journeys
from .services import add_dependency, assign_dossier, can_manage_dossier, can_view_dossier, grant_dossier_authority, revoke_dossier_authority, unassign_dossier


User = get_user_model()


class D3CollaborationAuthorityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="d3-owner", email="d3-owner@example.test", password="StrongPass2026!")
        self.alice = User.objects.create_user(username="d3-alice", email="d3-alice@example.test", password="StrongPass2026!")
        self.bob = User.objects.create_user(username="d3-bob", email="d3-bob@example.test", password="StrongPass2026!")
        self.dossier = Dossier.objects.create(title="Obtenir la bourse de Junior", created_by=self.owner, owner_profile=self.owner)

    def test_owner_mandate_and_assignment_are_independent(self):
        self.assertTrue(can_manage_dossier(self.owner, self.dossier))
        self.assertFalse(DossierAssignment.objects.filter(dossier=self.dossier, assignee=self.owner).exists())
        manager = grant_dossier_authority(actor=self.owner, dossier=self.dossier, profile=self.alice, role=SystemRoleCode.DOSSIER_MANAGER)
        self.assertTrue(can_manage_dossier(self.alice, self.dossier))
        self.assertFalse(DossierAssignment.objects.filter(dossier=self.dossier, assignee=self.alice).exists())
        assignment = assign_dossier(actor=self.owner, dossier=self.dossier, assignee=self.alice)
        self.assertEqual(assignment.status, DossierAssignmentStatus.ACTIVE)
        revoke_dossier_authority(actor=self.owner, dossier=self.dossier, mandate=manager)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, DossierAssignmentStatus.ACTIVE)
        self.assertFalse(can_manage_dossier(self.alice, self.dossier))

    def test_assignment_alone_never_grants_authority_and_service_requires_authority_first(self):
        with self.assertRaises(ValidationError): assign_dossier(actor=self.owner, dossier=self.dossier, assignee=self.alice)
        DossierAssignment.objects.create(dossier=self.dossier, assignee=self.alice, assigned_by=self.owner)
        self.assertFalse(can_view_dossier(self.alice, self.dossier))
        self.assertFalse(can_manage_dossier(self.alice, self.dossier))

    def test_active_assignment_is_unique_and_removal_keeps_history(self):
        grant_dossier_authority(actor=self.owner, dossier=self.dossier, profile=self.alice, role=SystemRoleCode.DOSSIER_MANAGER)
        assignment = assign_dossier(actor=self.owner, dossier=self.dossier, assignee=self.alice)
        with self.assertRaises(ValidationError): assign_dossier(actor=self.owner, dossier=self.dossier, assignee=self.alice)
        removed = unassign_dossier(actor=self.owner, dossier=self.dossier, assignment=assignment)
        self.assertEqual(removed.status, DossierAssignmentStatus.REMOVED); self.assertIsNotNone(removed.removed_at)
        replacement = assign_dossier(actor=self.owner, dossier=self.dossier, assignee=self.alice)
        self.assertNotEqual(replacement.pk, removed.pk)

    def test_limited_or_manage_only_actor_cannot_escalate_dossier_authority(self):
        grant_dossier_authority(actor=self.owner, dossier=self.dossier, profile=self.bob, role=SystemRoleCode.DOSSIER_VIEWER)
        with self.assertRaises(PermissionDenied): grant_dossier_authority(actor=self.bob, dossier=self.dossier, profile=self.bob, role=SystemRoleCode.DOSSIER_ADMIN)
        grant_dossier_authority(actor=self.owner, dossier=self.dossier, profile=self.alice, role=SystemRoleCode.DOSSIER_MANAGER)
        with self.assertRaises(PermissionDenied): grant_dossier_authority(actor=self.alice, dossier=self.dossier, profile=self.bob, role=SystemRoleCode.DOSSIER_VIEWER)

    def test_coordinator_dossier_authority_does_not_cross_journey_privacy_and_revocation_wins(self):
        grant = grant_dossier_authority(actor=self.owner, dossier=self.dossier, profile=self.alice, role=SystemRoleCode.DOSSIER_MANAGER)
        assignment = assign_dossier(actor=self.owner, dossier=self.dossier, assignee=self.alice)
        visible_activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="Visible pour Alice")
        visible_journey = Journey.objects.create(initiated_by=self.alice, beneficiary=self.owner, activity=visible_activity, workflow=WorkflowKind.SERVICE, status=JourneyStatus.DRAFT)
        visible_link = DossierJourneyLink.objects.create(dossier=self.dossier, journey=visible_journey, linked_by=self.owner)
        private_activity = Activity.objects.create(owner_profile=self.bob, created_by=self.bob, title="Journey privée Bob")
        private_journey = Journey.objects.create(initiated_by=self.bob, beneficiary=self.bob, activity=private_activity, workflow=WorkflowKind.SERVICE, status=JourneyStatus.DRAFT)
        private_link = DossierJourneyLink.objects.create(dossier=self.dossier, journey=private_journey, linked_by=self.bob)
        self.assertTrue(can_manage_dossier(self.alice, self.dossier))
        self.assertEqual(list(visible_linked_journeys(self.alice, self.dossier)), [visible_link])
        self.assertFalse(can_access_case(self.alice, private_journey))
        with self.assertRaises(PermissionDenied): add_dependency(actor=self.alice, dossier=self.dossier, dependent_link=visible_link, required_link=private_link)
        revoke_dossier_authority(actor=self.owner, dossier=self.dossier, mandate=grant)
        assignment.refresh_from_db(); self.assertEqual(assignment.status, DossierAssignmentStatus.ACTIVE); self.assertFalse(can_manage_dossier(self.alice, self.dossier))

    def test_membership_and_other_space_authority_do_not_cross_space_boundary(self):
        space_a = Organization.objects.create(name="Space A D3", created_by=self.owner); space_b = Organization.objects.create(name="Space B D3", created_by=self.owner)
        grant_space_role(profile=self.owner, space=space_a, role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner)
        dossier = Dossier.objects.create(title="Dossier Space A", created_by=self.owner, owning_space=space_a)
        team = Team.objects.create(organization=space_a, name="Equipe A", is_default=True); TeamMembership.objects.create(team=team, user=self.alice)
        self.assertFalse(can_view_dossier(self.alice, dossier)); self.assertFalse(can_manage_dossier(self.alice, dossier))
        grant_space_role(profile=self.alice, space=space_b, role=SystemRoleCode.SPACE_ADMIN, granted_by=self.owner)
        self.assertFalse(can_manage_dossier(self.alice, dossier))
        grant_dossier_authority(actor=self.owner, dossier=dossier, profile=self.alice, role=SystemRoleCode.DOSSIER_VIEWER)
        self.assertTrue(can_view_dossier(self.alice, dossier)); self.assertFalse(can_manage_dossier(self.alice, dossier))

    def test_external_beneficiary_remains_holder_not_authority_principal(self):
        users_before = User.objects.count(); mandates_before = Mandate.objects.count(); assignments_before = DossierAssignment.objects.count()
        external = ExternalBeneficiary.objects.create(display_name="Junior externe", created_by=self.owner)
        activity = Activity.objects.create(owner_profile=self.owner, created_by=self.owner, title="Démarche Junior")
        journey = Journey.objects.create(initiated_by=self.owner, external_beneficiary=external, activity=activity, workflow=WorkflowKind.SERVICE, status=JourneyStatus.DRAFT)
        DossierJourneyLink.objects.create(dossier=self.dossier, journey=journey, linked_by=self.owner)
        self.assertEqual(User.objects.count(), users_before); self.assertEqual(Mandate.objects.count(), mandates_before); self.assertEqual(DossierAssignment.objects.count(), assignments_before); self.assertTrue(journey.is_external_beneficiary)
