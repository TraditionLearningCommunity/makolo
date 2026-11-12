"""D5 acceptance: a canonical Dossier across Projects and actor lenses."""
from django.test import Client, TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.models import AuthorityScope, Role
from authorization.services import grant_dossier_role, grant_project_role, grant_space_role
from journeys.models import Journey, JourneyStatus, WorkflowKind
from objectives.models import DossierAssignmentStatus, DossierJourneyLink, ProjectDossierLink
from objectives.services import (
    assign_dossier, create_dossier, create_project, link_dossier_to_project,
    link_journey, revoke_dossier_authority,
)
from organizations.models import Organization, Team, TeamMembership


class D5CrossContextClosureTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="d5-owner")
        self.member = User.objects.create_user(username="d5-member")
        self.outsider = User.objects.create_user(username="d5-outsider")
        self.space_a = Organization.objects.create(
            name="D5 Space A", slug="d5-a", created_by=self.owner,
        )
        self.space_b = Organization.objects.create(
            name="D5 Space B", slug="d5-b", created_by=self.owner,
        )
        for space in (self.space_a, self.space_b):
            grant_space_role(
                profile=self.owner, space=space,
                role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
            )
        self.project_a1 = create_project(
            actor=self.owner, owning_space=self.space_a, title="A horizon 1",
        )
        self.project_a2 = create_project(
            actor=self.owner, owning_space=self.space_a, title="A horizon 2",
        )
        self.project_b = create_project(
            actor=self.owner, owning_space=self.space_b, title="B horizon",
        )
        self.dossier_a = create_dossier(
            actor=self.owner, owning_space=self.space_a, title="Resultat A",
        )
        self.dossier_b = create_dossier(
            actor=self.owner, owning_space=self.space_b, title="Resultat B",
        )
        for project, dossier in (
            (self.project_a1, self.dossier_a),
            (self.project_b, self.dossier_b),
        ):
            link_dossier_to_project(actor=self.owner, project=project, dossier=dossier)
        activity = Activity.objects.create(
            title="Action partagee", owner_profile=self.owner,
            created_by=self.owner,
        )
        self.shared_journey = Journey.objects.create(
            activity=activity, initiated_by=self.owner,
            beneficiary=self.member, workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.DRAFT,
        )
        for dossier in (self.dossier_a, self.dossier_b):
            link_journey(actor=self.owner, dossier=dossier, journey=self.shared_journey)
        project_manager = Role.objects.get(
            scope_type=AuthorityScope.PROJECT, code=SystemRoleCode.PROJECT_MANAGER,
        )
        project_viewer = Role.objects.get(
            scope_type=AuthorityScope.PROJECT, code=SystemRoleCode.PROJECT_VIEWER,
        )
        dossier_manager = Role.objects.get(
            scope_type=AuthorityScope.DOSSIER, code=SystemRoleCode.DOSSIER_MANAGER,
        )
        dossier_viewer = Role.objects.get(
            scope_type=AuthorityScope.DOSSIER, code=SystemRoleCode.DOSSIER_VIEWER,
        )
        for project in (self.project_a1, self.project_a2):
            grant_project_role(
                profile=self.member, project=project,
                role=project_manager, granted_by=self.owner,
            )
        grant_project_role(
            profile=self.member, project=self.project_b,
            role=project_viewer, granted_by=self.owner,
        )
        self.mandate_a = grant_dossier_role(
            profile=self.member, dossier=self.dossier_a,
            role=dossier_manager, granted_by=self.owner,
        )
        grant_dossier_role(
            profile=self.member, dossier=self.dossier_b,
            role=dossier_viewer, granted_by=self.owner,
        )
        self.assignment = assign_dossier(
            actor=self.owner, dossier=self.dossier_a, assignee=self.member,
        )
        team = Team.objects.create(
            organization=self.space_a, name="D5 Team", is_default=True,
        )
        TeamMembership.objects.create(team=team, user=self.outsider)
        self.client = APIClient()
        self.client.force_authenticate(user=self.member)

    def scope(self, space):
        return "?context=space&space=" + space.slug

    def dossier_url(self, dossier):
        return reverse("objectives_api:dossier-detail", args=[dossier.pk])

    def project_url(self, project):
        return reverse("objectives_api:project-detail", args=[project.pk])

    def test_space_coordination_candidates_include_mandates_not_team_authority(self):
        from objectives.forms import DossierAssignmentForm
        from objectives.models import DossierAssignment
        from objectives.selectors import collaboration_candidates_for_dossier

        # A person can hold a Dossier Mandate without joining a Space Team.
        mandate_only = User.objects.create_user(username="d5-mandate-only")
        role = Role.objects.get(
            scope_type=AuthorityScope.DOSSIER,
            code=SystemRoleCode.DOSSIER_MANAGER,
        )
        grant_dossier_role(
            profile=mandate_only, dossier=self.dossier_a,
            role=role, granted_by=self.owner,
        )
        self.assertFalse(TeamMembership.objects.filter(user=mandate_only).exists())
        candidates = collaboration_candidates_for_dossier(self.dossier_a)
        self.assertIn(mandate_only, candidates)
        # A Team member may be a grant candidate but cannot coordinate
        # unless an effective permission exists.
        self.assertIn(self.outsider, candidates)

        form = DossierAssignmentForm(dossier=self.dossier_a)
        allowed = set(form.fields["assignee"].queryset.values_list(
            "pk", flat=True,
        ))
        self.assertIn(mandate_only.pk, allowed)
        self.assertNotIn(self.outsider.pk, allowed)

        self.client.force_authenticate(user=self.owner)
        detail = self.client.get(
            self.dossier_url(self.dossier_a) + self.scope(self.space_a),
        )
        self.assertEqual(detail.status_code, 200, detail.data)
        projected = {
            row["id"] for row in detail.data["data"]["candidates"]["assignees"]
        }
        self.assertIn(str(mandate_only.pk), projected)
        self.assertNotIn(str(self.outsider.pk), projected)
        attempt = self.client.post(
            reverse("objectives_api:dossier-actions", args=[self.dossier_a.pk])
            + self.scope(self.space_a),
            {"action": "assignment_add", "assignee_id": str(self.outsider.pk)},
            format="json",
        )
        self.assertEqual(attempt.status_code, 400, attempt.data)
        self.assertFalse(DossierAssignment.objects.filter(
            dossier=self.dossier_a, assignee=self.outsider,
        ).exists())

    def test_dossier_people_links_follow_profile_visibility_not_mandates(self):
        from accounts.models import UserProfile

        self.client.force_authenticate(user=self.owner)
        url = self.dossier_url(self.dossier_a) + self.scope(self.space_a)
        private = self.client.get(url)
        self.assertEqual(private.status_code, 200, private.data)
        private_data = private.data["data"]
        assignment = next(
            row for row in private_data["assignments"]
            if row["profile_id"] == str(self.member.pk)
        )
        mandate = next(
            row for row in private_data["mandates"]
            if row["profile_id"] == str(self.member.pk)
        )
        preview = next(
            row for row in private_data["people_preview"]["people"]
            if row["profile_id"] == str(self.member.pk)
        )
        # A manager can see the delegated responsibility, not the private
        # Passport merely because it holds the corresponding Mandate.
        self.assertIsNone(assignment["profile_url"])
        self.assertIsNone(mandate["profile_url"])
        self.assertIsNone(preview["profile_url"])

        profile, _ = UserProfile.objects.get_or_create(user=self.member)
        profile.public_profile = True
        profile.save(update_fields=["public_profile"])
        public = self.client.get(url)
        self.assertEqual(public.status_code, 200, public.data)
        expected = reverse(
            "sharing:passport-profile", kwargs={"profile_id": self.member.pk},
        )
        public_data = public.data["data"]
        self.assertEqual(
            next(row for row in public_data["assignments"]
                 if row["profile_id"] == str(self.member.pk))["profile_url"],
            expected,
        )
        self.assertEqual(
            next(row for row in public_data["mandates"]
                 if row["profile_id"] == str(self.member.pk))["profile_url"],
            expected,
        )
        self.assertEqual(
            next(row for row in public_data["people_preview"]["people"]
                 if row["profile_id"] == str(self.member.pk))["profile_url"],
            expected,
        )

    def test_people_preview_only_contains_visible_profiles_and_deduplicates(self):
        # The member is an Assignment holder and a Dossier mandate holder;
        # without authority to manage mandates, only their own Assignment
        # must be disclosed in the compact summary.
        url = self.dossier_url(self.dossier_a) + self.scope(self.space_a)
        self.client.force_authenticate(user=self.member)
        own = self.client.get(url)
        self.assertEqual(own.status_code, 200, own.data)
        people = own.data["data"]["people_preview"]
        self.assertEqual(people["remaining"], 0)
        self.assertEqual(
            [entry["profile_id"] for entry in people["people"]],
            [str(self.member.pk)],
        )
        self.assertEqual(own.data["data"]["mandates"], [])

        # The owner sees both Assignment and Mandate facts for the member,
        # but the preview must show that human Profile only once.
        self.client.force_authenticate(user=self.owner)
        manager = self.client.get(url)
        self.assertEqual(manager.status_code, 200, manager.data)
        preview = manager.data["data"]["people_preview"]
        ids = [entry["profile_id"] for entry in preview["people"]]
        self.assertEqual(ids.count(str(self.member.pk)), 1)
        self.assertEqual(preview["remaining"], 0)
        self.assertTrue(manager.data["data"]["mandates"])
        self.assertTrue(manager.data["data"]["assignments"])

    def test_people_preview_caps_at_four_visible_distinct_profiles(self):
        role = Role.objects.get(
            scope_type=AuthorityScope.DOSSIER,
            code=SystemRoleCode.DOSSIER_VIEWER,
        )
        for index in range(4):
            colleague = User.objects.create_user(username=f"d5-colleague-{index}")
            grant_dossier_role(
                profile=colleague,
                dossier=self.dossier_a,
                role=role,
                granted_by=self.owner,
            )

        self.client.force_authenticate(user=self.owner)
        result = self.client.get(
            self.dossier_url(self.dossier_a) + self.scope(self.space_a),
        )
        self.assertEqual(result.status_code, 200, result.data)
        preview = result.data["data"]["people_preview"]
        ids = [row["profile_id"] for row in preview["people"]]
        self.assertEqual(len(ids), 4)
        self.assertEqual(len(set(ids)), 4)
        self.assertEqual(preview["remaining"], 1)
        self.assertIn(str(self.member.pk), ids)

        # A single mandate holder sees neither an owner-scoped roster nor
        # the count of hidden people in the same Dossier.
        self.client.force_authenticate(user=self.member)
        limited = self.client.get(
            self.dossier_url(self.dossier_a) + self.scope(self.space_a),
        )
        self.assertEqual(limited.status_code, 200, limited.data)
        preview = limited.data["data"]["people_preview"]
        self.assertEqual(
            [row["profile_id"] for row in preview["people"]],
            [str(self.member.pk)],
        )
        self.assertEqual(preview["remaining"], 0)

    def test_move_preserves_dossier_and_shared_journey_identities(self):
        a = self.client.get(self.dossier_url(self.dossier_a) + self.scope(self.space_a))
        b = self.client.get(self.dossier_url(self.dossier_b) + self.scope(self.space_b))
        self.assertEqual(a.status_code, 200, a.data)
        self.assertEqual(b.status_code, 200, b.data)
        self.assertEqual(a.data["data"]["viewer"]["id"], str(self.member.pk))
        self.assertIn("dossier.edit", a.data["data"]["capabilities"])
        self.assertNotIn("dossier.edit", b.data["data"]["capabilities"])
        for detail in (a, b):
            self.assertEqual(
                {row["id"] for row in detail.data["data"]["visible_journeys"]},
                {str(self.shared_journey.pk)},
            )
        project = self.client.get(
            self.project_url(self.project_a1) + self.scope(self.space_a),
        )
        self.assertEqual(project.status_code, 200, project.data)
        targets = {row["id"] for row in project.data["data"]["move_targets"]}
        self.assertIn(str(self.project_a2.pk), targets)
        self.assertNotIn(str(self.project_b.pk), targets)

        move = self.client.post(
            reverse(
                "objectives_api:project-dossier-action",
                args=[self.project_a1.pk, self.dossier_a.pk],
            ) + self.scope(self.space_a),
            {"action": "move", "target_project_id": str(self.project_a2.pk)},
            format="json",
        )
        self.assertEqual(move.status_code, 200, move.data)
        self.assertEqual(
            ProjectDossierLink.objects.get(
                dossier=self.dossier_a, is_active=True,
            ).project_id, self.project_a2.pk,
        )
        self.assertEqual(
            ProjectDossierLink.objects.filter(dossier=self.dossier_a).count(), 2,
        )
        self.assertEqual(
            DossierJourneyLink.objects.filter(
                dossier=self.dossier_a, journey=self.shared_journey, is_active=True,
            ).count(), 1,
        )
        after = self.client.get(
            self.dossier_url(self.dossier_a) + self.scope(self.space_a),
        )
        self.assertEqual(after.status_code, 200, after.data)
        self.assertEqual(after.data["data"]["identity"], a.data["data"]["identity"])
        self.assertEqual(
            after.data["data"]["parent_project"]["id"], str(self.project_a2.pk),
        )
        self.assertEqual(
            self.client.get(
                self.dossier_url(self.dossier_a) + self.scope(self.space_b),
            ).status_code, 404,
        )

    def test_revoke_dossier_mandate_keeps_assignment_but_hides_dossier(self):
        revoke_dossier_authority(
            actor=self.owner, dossier=self.dossier_a, mandate=self.mandate_a,
        )
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.status, DossierAssignmentStatus.ACTIVE)
        self.assertEqual(
            self.client.get(
                self.dossier_url(self.dossier_a) + self.scope(self.space_a),
            ).status_code, 404,
        )
        self.assertEqual(
            self.client.post(
                reverse("objectives_api:dossier-actions", args=[self.dossier_a.pk])
                + self.scope(self.space_a),
                {"action": "lifecycle", "lifecycle": "active"}, format="json",
            ).status_code, 404,
        )
        project = self.client.get(
            self.project_url(self.project_a1) + self.scope(self.space_a),
        )
        self.assertEqual(project.status_code, 200, project.data)
        self.assertNotIn(
            str(self.dossier_a.pk),
            [row["id"] for row in project.data["data"]["visible_dossiers"]],
        )
        self.assertEqual(
            self.client.get(
                self.dossier_url(self.dossier_b) + self.scope(self.space_b),
            ).status_code, 200,
        )
        self.assertEqual(
            self.client.patch(
                self.dossier_url(self.dossier_b) + self.scope(self.space_b),
                {"title": "Interdit"}, format="json",
            ).status_code, 403,
        )
        self.dossier_b.refresh_from_db()
        self.assertEqual(self.dossier_b.title, "Resultat B")

    def test_scoped_organizer_retracts_dossier_after_mandate_revocation(self):
        organizer_url = reverse("objectives_api:organizer")
        before_a = self.client.get(organizer_url + self.scope(self.space_a))
        before_b = self.client.get(organizer_url + self.scope(self.space_b))
        self.assertEqual(before_a.status_code, 200, before_a.data)
        self.assertEqual(before_b.status_code, 200, before_b.data)

        def identities(response):
            return {
                (row["kind"], row["id"]) for row in response.data["data"]["items"]
            }

        self.assertIn(("dossier", str(self.dossier_a.pk)), identities(before_a))
        self.assertIn(("dossier", str(self.dossier_b.pk)), identities(before_b))
        self.assertIn(
            ("journey", str(self.shared_journey.pk)), identities(before_a),
        )
        revoke_dossier_authority(
            actor=self.owner, dossier=self.dossier_a, mandate=self.mandate_a,
        )

        after_a = self.client.get(organizer_url + self.scope(self.space_a))
        after_b = self.client.get(organizer_url + self.scope(self.space_b))
        self.assertEqual(after_a.status_code, 200, after_a.data)
        self.assertEqual(after_b.status_code, 200, after_b.data)
        self.assertIn(("project", str(self.project_a1.pk)), identities(after_a))
        self.assertNotIn(("dossier", str(self.dossier_a.pk)), identities(after_a))
        self.assertNotIn(
            ("journey", str(self.shared_journey.pk)), identities(after_a),
        )
        self.assertIn(("dossier", str(self.dossier_b.pk)), identities(after_b))
        self.assertIn(
            ("journey", str(self.shared_journey.pk)), identities(after_b),
        )

    def test_private_journey_is_hidden_and_web_uses_same_dossier_authority(self):
        private_activity = Activity.objects.create(
            title="D5 private action", owner_profile=self.owner,
            created_by=self.owner,
        )
        private_journey = Journey.objects.create(
            activity=private_activity, initiated_by=self.owner,
            beneficiary=self.owner, workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.DRAFT,
        )
        link_journey(
            actor=self.owner, dossier=self.dossier_a, journey=private_journey,
        )
        api = self.client.get(
            self.dossier_url(self.dossier_a) + self.scope(self.space_a),
        )
        self.assertEqual(api.status_code, 200, api.data)
        visible = {
            row["id"] for row in api.data["data"]["visible_journeys"]
        }
        self.assertIn(str(self.shared_journey.pk), visible)
        self.assertNotIn(str(private_journey.pk), visible)
        web_url = reverse(
            "objectives:dossier-detail", args=[self.dossier_a.pk],
        )
        web = Client()
        web.force_login(self.member)
        self.assertEqual(web.get(web_url).status_code, 200)
        revoke_dossier_authority(
            actor=self.owner, dossier=self.dossier_a, mandate=self.mandate_a,
        )
        self.assertEqual(web.get(web_url).status_code, 404)
        self.assertEqual(
            self.client.get(
                self.dossier_url(self.dossier_a) + self.scope(self.space_a),
            ).status_code, 404,
        )

    def test_membership_only_and_cross_space_action_are_never_authority(self):
        self.client.force_authenticate(user=self.outsider)
        for resource in (
            self.project_url(self.project_a1),
            self.dossier_url(self.dossier_a),
        ):
            self.assertEqual(
                self.client.get(resource + self.scope(self.space_a)).status_code,
                404,
            )
        self.client.force_authenticate(user=self.member)
        self.assertEqual(
            self.client.get(
                self.project_url(self.project_b) + self.scope(self.space_a),
            ).status_code, 404,
        )
        self.assertEqual(
            self.client.post(
                reverse(
                    "objectives_api:project-dossier-action",
                    args=[self.project_b.pk, self.dossier_b.pk],
                ) + self.scope(self.space_b),
                {"action": "unlink"}, format="json",
            ).status_code, 403,
        )
        self.assertEqual(
            self.client.post(
                reverse(
                    "objectives_api:project-dossier-action",
                    args=[self.project_a1.pk, self.dossier_a.pk],
                ) + self.scope(self.space_a),
                {"action": "move", "target_project_id": str(self.project_b.pk)},
                format="json",
            ).status_code, 404,
        )
        self.assertEqual(
            ProjectDossierLink.objects.get(
                dossier=self.dossier_a, is_active=True,
            ).project_id, self.project_a1.pk,
        )
