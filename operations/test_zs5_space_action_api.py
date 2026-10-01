from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role, revoke_mandate
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus
from scanner.models import ScannerAssignment


class ZS5SpaceActionProjectionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="zs5-owner", email="zs5-owner@test.local", password="x"
        )
        self.operator = User.objects.create_user(
            username="zs5-operator", email="zs5-operator@test.local", password="x"
        )
        self.outsider = User.objects.create_user(
            username="zs5-outsider", email="zs5-outsider@test.local", password="x"
        )
        self.space = Organization.objects.create(
            name="ZS5 Space", slug="zs5-space", created_by=self.owner
        )
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        self.admin_mandate = grant_space_role(
            profile=self.admin,
            space=self.space,
            role=SystemRoleCode.SPACE_ADMIN,
            granted_by=self.owner,
        )
        self.activity = Activity.objects.create(
            title="Départ ZS5",
            space=self.space,
            created_by=self.owner,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() - timedelta(minutes=30),
            end_at=timezone.now() + timedelta(hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.other_activity = Activity.objects.create(
            title="Autre activité ZS5",
            space=self.space,
            created_by=self.owner,
        )
        self.other_occurrence = Occurrence.objects.create(
            activity=self.other_activity,
            start_at=timezone.now() - timedelta(minutes=20),
            end_at=timezone.now() + timedelta(hours=1),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.operator_mandate = grant_activity_role(
            profile=self.operator,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
        )
        self.client = APIClient()

    def test_space_day_of_is_occurrence_scoped_and_activity_authority_is_bounded(self):
        self.client.force_authenticate(self.operator)
        response = self.client.get(
            f"/api/v1/operations/occurrences/{self.occurrence.pk}/day-of/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data["data"]
        self.assertEqual(data["identity"], {"kind": "occurrence", "id": str(self.occurrence.pk)})
        self.assertEqual(data["context"]["authority"] if "authority" in data["context"] else data["context"]["perspective"], "operator")
        self.assertNotIn("space_live", data)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertIsInstance(data["capacity"], list)
        self.assertIsInstance(data["placement"], list)
        self.assertIsInstance(data["queues"], list)
        self.assertIsInstance(data["checkpoints"], list)
        self.assertEqual(data["incidents"]["truth"], "unavailable")
        self.assertEqual(data["incidents"]["items"], [])

        denied = self.client.get(
            f"/api/v1/operations/occurrences/{self.other_occurrence.pk}/day-of/"
        )
        self.assertEqual(denied.status_code, 404)

    def test_direct_space_authority_can_open_occurrence_day_of(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(
            f"/api/v1/operations/occurrences/{self.occurrence.pk}/day-of/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["context"]["perspective"], "space")

    def test_day_of_rejects_unauthenticated_outsider_and_non_current_occurrence(self):
        self.assertEqual(
            self.client.get(
                f"/api/v1/operations/occurrences/{self.occurrence.pk}/day-of/"
            ).status_code,
            401,
        )
        self.client.force_authenticate(self.outsider)
        self.assertEqual(
            self.client.get(
                f"/api/v1/operations/occurrences/{self.occurrence.pk}/day-of/"
            ).status_code,
            404,
        )

        future = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=7),
            end_at=timezone.now() + timedelta(days=7, hours=1),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.client.force_authenticate(self.operator)
        self.assertEqual(
            self.client.get(
                f"/api/v1/operations/occurrences/{future.pk}/day-of/"
            ).status_code,
            404,
        )

    def test_multiple_current_occurrences_remain_independent(self):
        second = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() - timedelta(minutes=10),
            end_at=timezone.now() + timedelta(hours=1),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.client.force_authenticate(self.operator)
        first = self.client.get(
            f"/api/v1/operations/occurrences/{self.occurrence.pk}/day-of/"
        )
        other = self.client.get(
            f"/api/v1/operations/occurrences/{second.pk}/day-of/"
        )
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(other.status_code, 200, other.data)
        self.assertNotEqual(
            first.data["data"]["identity"]["id"],
            other.data["data"]["identity"]["id"],
        )
        self.assertNotIn("live", first.data["data"]["context"]["space"])

    def test_scanner_assignment_alone_never_grants_scanner_context(self):
        ScannerAssignment.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            agent=self.outsider,
            assigned_by=self.owner,
            label="Contrôle terrain",
        )
        self.client.force_authenticate(self.outsider)
        response = self.client.get(
            f"/api/v1/scanner/occurrences/{self.occurrence.pk}/context/"
        )
        self.assertEqual(response.status_code, 404)

    def test_scanner_permission_opens_focused_context_without_secret(self):
        grant_activity_role(
            profile=self.outsider,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_SCANNER,
            granted_by=self.owner,
        )
        ScannerAssignment.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            agent=self.outsider,
            assigned_by=self.owner,
            label="Contrôle terrain",
        )
        self.client.force_authenticate(self.outsider)
        response = self.client.get(
            f"/api/v1/scanner/occurrences/{self.occurrence.pk}/context/"
        )
        self.assertEqual(response.status_code, 200, response.data)
        data = response.data["data"]
        self.assertEqual(data["identity"]["id"], str(self.occurrence.pk))
        self.assertEqual(data["control"]["authority"], "canonical_permission")
        body = response.content.decode().casefold()
        self.assertNotIn("token", body)
        self.assertNotIn("credential", body)
        self.assertNotIn("qr", body)
        # A generic Activity has no canonical non-Event scan POST endpoint yet.
        self.assertEqual(data["next_scan"]["state"], "unavailable")
        self.assertNotIn("scan", data["capabilities"])

    def test_toctou_revalidates_revoked_activity_authority(self):
        self.client.force_authenticate(self.operator)
        allowed = self.client.get(
            f"/api/v1/operations/occurrences/{self.occurrence.pk}/day-of/"
        )
        self.assertEqual(allowed.status_code, 200, allowed.data)
        revoke_mandate(mandate=self.operator_mandate, actor=self.owner)
        denied = self.client.get(
            f"/api/v1/operations/occurrences/{self.occurrence.pk}/day-of/"
        )
        self.assertEqual(denied.status_code, 404)


class ZS5SpaceMarkTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="zs5-mark-owner", email="zs5-mark-owner@test.local", password="x"
        )
        self.member = User.objects.create_user(
            username="zs5-mark-member", email="zs5-mark-member@test.local", password="x"
        )
        self.target = User.objects.create_user(
            username="zs5-mark-target", email="zs5-mark-target@test.local", password="x"
        )
        self.admin = User.objects.create_user(
            username="zs5-mark-admin", email="zs5-mark-admin@test.local", password="x"
        )
        self.space = Organization.objects.create(
            name="ZS5 Mark Space", slug="zs5-mark-space", created_by=self.owner
        )
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        team = Team.objects.create(
            organization=self.space,
            name="ZS5 Team",
            is_default=True,
            is_active=True,
        )
        TeamMembership.objects.create(
            team=team,
            user=self.member,
            status=TeamMembershipStatus.ACTIVE,
        )
        self.client = APIClient()

    def _post(self, user, text, context=None):
        self.client.force_authenticate(user)
        return self.client.post(
            f"/api/v1/organizations/workspaces/{self.space.slug}/mark/",
            {
                "input": {"kind": "text", "value": text},
                "context": context or {},
            },
            format="json",
        )

    def test_mark_is_explicit_space_actor_and_membership_is_not_authority(self):
        response = self._post(self.owner, "Ouvre l'équipe")
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["meta"]["projection"], "space.mark")
        self.assertEqual(response.data["meta"]["scope"], "space")
        self.assertEqual(response.data["data"]["handoff"]["owner"], "organizations")
        self.assertEqual(response["Cache-Control"], "private, no-store")

        denied = self._post(self.member, "Ouvre l'équipe")
        self.assertEqual(denied.status_code, 404)

    def test_responsibility_does_not_create_authority_and_authority_spoofing_is_rejected(self):
        response = self._post(
            self.owner,
            "Ouvre l'équipe",
            context={"responsibility": "Finance"},
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["result"]["responsibility"], "Finance")

        spoof = self._post(
            self.owner,
            "Ouvre l'équipe",
            context={"permission": "space.team.manage"},
        )
        self.assertEqual(spoof.status_code, 400)

    def test_mark_uses_bounded_clarification_and_honest_unsupported_state(self):
        clarification = self._post(self.owner, "Ouvre le scanner")
        self.assertEqual(clarification.status_code, 200, clarification.data)
        self.assertEqual(clarification.data["data"]["state"], "needs_clarification")
        self.assertEqual(
            clarification.data["data"]["question"]["code"],
            "which_occurrence",
        )

        unsupported = self._post(self.owner, "Crée une commande")
        self.assertEqual(unsupported.status_code, 200, unsupported.data)
        self.assertEqual(unsupported.data["data"]["state"], "unsupported")
        self.assertEqual(
            unsupported.data["data"]["result"]["reason"],
            "owner_handoff_not_available_on_base",
        )

    def test_team_mutation_requires_confirmation_uses_owner_service_and_replays_idempotently(self):
        context = {
            "team_member": {
                "email": self.target.email,
                "role": "finance",
            }
        }
        pending = self._post(self.owner, "Ajoute Paul dans l'équipe", context=context)
        self.assertEqual(pending.status_code, 200, pending.data)
        self.assertEqual(pending.data["data"]["state"], "needs_confirmation")
        self.assertFalse(
            TeamMembership.objects.filter(
                team__organization=self.space,
                user=self.target,
            ).exists()
        )

        confirmed = {
            **context,
            "confirmation": {
                "code": "add_team_member",
                "email": self.target.email,
                "role": "finance",
            },
        }
        first = self._post(self.owner, "Ajoute Paul dans l'équipe", context=confirmed)
        second = self._post(self.owner, "Ajoute Paul dans l'équipe", context=confirmed)
        self.assertEqual(first.status_code, 200, first.data)
        self.assertEqual(first.data["data"]["state"], "completed")
        self.assertEqual(second.data["data"]["state"], "completed")
        self.assertEqual(
            first.data["data"]["result"]["id"],
            second.data["data"]["result"]["id"],
        )
        self.assertEqual(
            TeamMembership.objects.filter(
                team__organization=self.space,
                user=self.target,
            ).count(),
            1,
        )

    def test_mark_confirmation_revalidates_authority_after_revocation(self):
        context = {
            "team_member": {
                "email": self.target.email,
                "role": "finance",
            }
        }
        pending = self._post(self.admin, "Ajoute Paul dans l'équipe", context=context)
        self.assertEqual(pending.status_code, 200, pending.data)
        self.assertEqual(pending.data["data"]["state"], "needs_confirmation")

        revoke_mandate(mandate=self.admin_mandate, actor=self.owner)
        confirmed = {
            **context,
            "confirmation": {
                "code": "add_team_member",
                "email": self.target.email,
                "role": "finance",
            },
        }
        denied = self._post(self.admin, "Ajoute Paul dans l'équipe", context=confirmed)
        self.assertEqual(denied.status_code, 404)
        self.assertFalse(
            TeamMembership.objects.filter(
                team__organization=self.space,
                user=self.target,
            ).exists()
        )

    def test_non_text_input_is_unsupported_without_persistence(self):
        self.client.force_authenticate(self.owner)
        response = self.client.post(
            f"/api/v1/organizations/workspaces/{self.space.slug}/mark/",
            {
                "input": {"kind": "file_reference", "value": "opaque"},
                "context": {},
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["data"]["state"], "unsupported")
