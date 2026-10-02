from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from activities.models import Activity, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import (
    grant_activity_role,
    grant_space_role,
    revoke_mandate,
)
from organizations.models import Organization
from scanner.models import ScannerAssignment


class WS5SpaceDayOfLiveScannerMarkWebTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.owner = User.objects.create_user(
            username="ws5-owner", email="ws5-owner@test.local", password="x"
        )
        self.operator = User.objects.create_user(
            username="ws5-operator", email="ws5-operator@test.local", password="x"
        )
        self.scanner = User.objects.create_user(
            username="ws5-scanner", email="ws5-scanner@test.local", password="x"
        )
        self.assigned_only = User.objects.create_user(
            username="ws5-assigned", email="ws5-assigned@test.local", password="x"
        )
        self.outsider = User.objects.create_user(
            username="ws5-outsider", email="ws5-outsider@test.local", password="x"
        )
        self.platform = User.objects.create_user(
            username="ws5-platform", email="ws5-platform@test.local", password="x"
        )
        self.space = Organization.objects.create(
            name="WS5 Transport", slug="ws5-transport", created_by=self.owner
        )
        self.other_space = Organization.objects.create(
            name="WS5 Foreign", slug="ws5-foreign", created_by=self.owner
        )
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        self.activity = Activity.objects.create(
            title="Départ Lubumbashi → Kolwezi",
            slug="depart-lubumbashi-kolwezi-ws5",
            created_by=self.owner,
            space=self.space,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="Départ 08 h",
            start_at=self.now - timedelta(minutes=10),
            end_at=self.now + timedelta(hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.future = Occurrence.objects.create(
            activity=self.activity,
            label="Départ semaine prochaine",
            start_at=self.now + timedelta(days=7),
            end_at=self.now + timedelta(days=7, hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.other_activity = Activity.objects.create(
            title="Activité étrangère",
            slug="activite-etrangere-ws5",
            created_by=self.owner,
            space=self.other_space,
        )
        self.other_occurrence = Occurrence.objects.create(
            activity=self.other_activity,
            label="Occurrence étrangère",
            start_at=self.now - timedelta(minutes=5),
            end_at=self.now + timedelta(hours=1),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.operator_mandate = grant_activity_role(
            profile=self.operator,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
        )
        self.scanner_mandate = grant_activity_role(
            profile=self.scanner,
            activity=self.activity,
            role=SystemRoleCode.ACTIVITY_SCANNER,
            granted_by=self.owner,
        )
        ScannerAssignment.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            agent=self.assigned_only,
            assigned_by=self.owner,
            label="Contrôle terrain sans autorité",
        )
        grant_platform_role(
            profile=self.platform,
            role=SystemRoleCode.PLATFORM_ADMIN,
            granted_by=self.platform,
        )

    def _url(self, name, occurrence=None):
        kwargs = {"slug": self.space.slug}
        if occurrence is not None:
            kwargs["occurrence_id"] = occurrence.pk
        return reverse(name, kwargs=kwargs)

    def test_day_of_direct_url_requires_real_space_or_activity_authority(self):
        url = self._url("organizations:space-occurrence-day-of", self.occurrence)
        visitor = self.client.get(url)
        self.assertEqual(visitor.status_code, 302)

        for actor in (self.outsider, self.assigned_only, self.platform):
            self.client.force_login(actor)
            self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_login(self.operator)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Jour J")
        self.assertContains(response, "Départ 08 h")
        self.assertContains(
            response,
            self._url("organizations:space-occurrence-live", self.occurrence),
            html=False,
        )

    def test_day_of_is_occurrence_scoped_and_non_current_is_not_promoted(self):
        self.client.force_login(self.operator)
        self.assertEqual(
            self.client.get(
                self._url("organizations:space-occurrence-day-of", self.future)
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                reverse(
                    "organizations:space-occurrence-day-of",
                    kwargs={
                        "slug": self.space.slug,
                        "occurrence_id": self.other_occurrence.pk,
                    },
                )
            ).status_code,
            404,
        )

    def test_live_is_server_projection_and_never_frontend_clock_synthesis(self):
        self.client.force_login(self.operator)
        response = self.client.get(
            self._url("organizations:space-occurrence-live", self.occurrence)
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["projection"]["perspective"], "operator")
        self.assertEqual(response.context["projection"]["phase"], "live")
        self.assertContains(
            response,
            "Une planification n’est jamais présentée comme une observation live.",
        )
        self.assertNotContains(response, "Date.now")
        self.assertNotContains(response, "setInterval")

    def test_scanner_assignment_is_not_authority_and_generic_owner_gap_is_honest(self):
        url = self._url("organizations:space-occurrence-scanner", self.occurrence)

        self.client.force_login(self.assigned_only)
        self.assertEqual(self.client.get(url).status_code, 404)

        self.client.force_login(self.scanner)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["scanner_available"])
        self.assertContains(response, "Scanner indisponible pour cette Occurrence")
        self.assertNotContains(response, 'id="scanner-console"')

        action = self.client.post(
            self._url(
                "organizations:space-occurrence-scanner-action",
                self.occurrence,
            ),
            {"token": "not-a-real-credential"},
        )
        self.assertEqual(action.status_code, 409)
        self.assertEqual(action.json()["result"], "unavailable")

    def test_scanner_get_does_not_survive_authority_revocation_on_post(self):
        self.client.force_login(self.scanner)
        url = self._url("organizations:space-occurrence-scanner", self.occurrence)
        self.assertEqual(self.client.get(url).status_code, 200)

        revoke_mandate(mandate=self.scanner_mandate, actor=self.owner)
        denied = self.client.post(
            self._url(
                "organizations:space-occurrence-scanner-action",
                self.occurrence,
            ),
            {"token": "stale-context-token"},
        )
        self.assertEqual(denied.status_code, 404)

    def test_scanner_camera_is_opt_in_and_keeps_non_camera_fallbacks(self):
        self.client.force_login(self.scanner)
        response = self.client.get(
            self._url("organizations:space-occurrence-scanner", self.occurrence)
        )
        self.assertEqual(response.status_code, 200)
        # Generic Activity has no owner scan endpoint, so the interactive scanner
        # is intentionally absent rather than faked.
        self.assertNotContains(response, 'data-auto-start="true"')

    def test_space_mark_hands_day_of_to_ws5_without_client_authority(self):
        self.client.force_login(self.owner)
        url = self._url("organizations:space-mark")
        response = self.client.post(
            url,
            {
                "value": "Ouvre le Jour J",
                "occurrence_id": str(self.occurrence.pk),
                "permission": "space.manage",
                "is_admin": "true",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["mark_result"]["state"], "resolved")
        self.assertEqual(
            response.context["mark_handoff_url"],
            self._url("organizations:space-occurrence-day-of", self.occurrence),
        )
        self.assertNotContains(response, "space.manage")
        self.assertNotContains(response, "is_admin")

    def test_space_mark_does_not_turn_activity_context_into_team_authority(self):
        self.client.force_login(self.operator)
        response = self.client.post(
            self._url("organizations:space-mark"),
            {
                "value": "Ouvre l'équipe",
                "permission": "space.team.manage",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["mark_result"]["state"], "forbidden")
        self.assertContains(response, "autorité Team réelle")

    def test_space_mark_preserves_honest_unsupported_owner_handoff(self):
        self.client.force_login(self.owner)
        response = self.client.post(
            self._url("organizations:space-mark"),
            {"value": "Crée une commande"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["mark_result"]["state"], "unsupported")
        self.assertContains(response, "n’est pas encore stable")

    def test_mark_supported_team_mutation_keeps_confirmation_boundary(self):
        target = User.objects.create_user(
            username="ws5-target", email="ws5-target@test.local", password="x"
        )
        self.client.force_login(self.owner)
        first = self.client.post(
            self._url("organizations:space-mark"),
            {"value": "Ajoute un membre"},
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(
            first.context["mark_result"]["state"],
            "needs_clarification",
        )
        self.assertContains(first, 'name="team_member_email"')
        self.assertContains(first, 'name="team_member_role"')

        second = self.client.post(
            self._url("organizations:space-mark"),
            {
                "value": "Ajoute un membre",
                "team_member_email": target.email,
                "team_member_role": "finance",
            },
        )
        self.assertEqual(second.context["mark_result"]["state"], "needs_confirmation")
        self.assertContains(second, "Confirmation nécessaire")
        self.assertContains(second, "Confirmer cette action")

    def test_ended_occurrence_closes_day_of_naturally_without_archive_route(self):
        self.occurrence.status = OccurrenceStatus.COMPLETED
        self.occurrence.start_at = self.now - timedelta(hours=3)
        self.occurrence.end_at = self.now - timedelta(minutes=5)
        self.occurrence.save(
            update_fields=["status", "start_at", "end_at", "updated_at"]
        )
        self.client.force_login(self.operator)
        response = self.client.get(
            self._url("organizations:space-occurrence-day-of", self.occurrence)
        )
        self.assertEqual(response.status_code, 404)
