from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import grant_activity_role, grant_space_role, revoke_mandate
from groups.models import Group, GroupMembership, GroupMembershipStatus
from scanner.models import ScannerAssignment

from .models import Organization, SpaceArchetype, Team, TeamMembership, TeamMembershipStatus


class WS1SpaceWebFoundationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="ws1-owner", email="ws1-owner@test.local", password="x"
        )
        self.member = User.objects.create_user(
            username="ws1-member", email="ws1-member@test.local", password="x"
        )
        self.platform = User.objects.create_user(
            username="ws1-platform", email="ws1-platform@test.local", password="x"
        )
        self.space = Organization.objects.create(
            name="WS1 Académie",
            slug="ws1-academie",
            archetype=SpaceArchetype.EDUCATION,
            created_by=self.owner,
        )
        self.owner_mandate = grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )

    def space_url(self, name="organizations:console-entry", **query):
        url = reverse(name, kwargs={"slug": self.space.slug})
        if not query:
            return url
        from urllib.parse import urlencode

        return f"{url}?{urlencode(query)}"

    def test_visitor_is_sent_to_login_and_outsider_is_privacy_safe(self):
        response = self.client.get(self.space_url())
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:login"), response.url)

        outsider = User.objects.create_user(
            username="ws1-outsider", email="ws1-outsider@test.local", password="x"
        )
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(self.space_url()).status_code, 404)

    def test_space_shell_has_five_contextual_primary_destinations(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.space_url())
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        mobile = html.split('id="mobile-primary-nav"', 1)[1].split("</nav>", 1)[0]
        desktop = html.split('class="mk-mature-rail"', 1)[1].split("</nav>", 1)[0]

        for label in ("Maintenant", "Découvrir", "Makolo", "Programmes", "Nous"):
            self.assertIn(label, mobile)
            self.assertIn(label, desktop)
        self.assertNotIn(">En cours<", mobile)
        self.assertNotIn(">Moi<", mobile)
        self.assertIn('data-mk-runtime-scope="space:', html)
        self.assertIn("Agit pour WS1 Académie", html)

    def test_personal_navigation_remains_the_same_five_n1(self):
        self.client.force_login(self.owner)
        response = self.client.get(reverse("core:participant-home"))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        mobile = html.split('id="mobile-primary-nav"', 1)[1].split("</nav>", 1)[0]

        for label in ("Maintenant", "Découvrir", "Makolo", "En cours", "Moi"):
            self.assertIn(label, mobile)
        self.assertNotIn(">Nous<", mobile)
        self.assertNotIn(">Programmes<", mobile)

    def test_archetype_business_label_comes_from_server_projection(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.space_url("organizations:space-work"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Programmes")
        self.assertEqual(response.context["space_business_label"], "Programmes")

    def test_valid_activity_responsibility_is_preserved_across_space_navigation(self):
        activity = Activity.objects.create(
            title="Programme Génie civil",
            slug="programme-genie-civil",
            created_by=self.owner,
            space=self.space,
        )
        mandate = grant_activity_role(
            profile=self.owner,
            activity=activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner,
        )
        key = f"mandate:{mandate.pk}"

        self.client.force_login(self.owner)
        response = self.client.get(self.space_url(responsibility=key))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_responsibility"]["key"], key)
        self.assertContains(
            response,
            f"{reverse('organizations:space-discover', kwargs={'slug': self.space.slug})}?responsibility=",
            html=False,
        )

    def test_foreign_or_revoked_responsibility_never_falls_back_silently(self):
        other = Organization.objects.create(
            name="Autre WS1", slug="autre-ws1", created_by=self.owner
        )
        foreign = grant_space_role(
            profile=self.owner,
            space=other,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )

        activity = Activity.objects.create(
            title="Responsabilité révoquée",
            slug="responsabilite-revoquee",
            created_by=self.owner,
            space=self.space,
        )
        revoked = grant_activity_role(
            profile=self.owner,
            activity=activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner,
        )
        revoke_mandate(revoked, revoked_by=self.owner)

        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(
                self.space_url(responsibility=f"mandate:{foreign.pk}")
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.get(
                self.space_url(responsibility=f"mandate:{revoked.pk}")
            ).status_code,
            404,
        )

    def test_membership_group_assignment_and_platform_authority_do_not_open_space(self):
        team = Team.objects.create(
            organization=self.space,
            name="Équipe WS1",
            is_default=True,
            is_active=True,
        )
        TeamMembership.objects.create(
            team=team,
            user=self.member,
            status=TeamMembershipStatus.ACTIVE,
        )
        group = Group.objects.create(
            name="Groupe WS1",
            slug="groupe-ws1",
            space=self.space,
            created_by=self.owner,
        )
        GroupMembership.objects.create(
            group=group,
            profile=self.member,
            status=GroupMembershipStatus.ACTIVE,
        )
        activity = Activity.objects.create(
            title="Contrôle WS1",
            slug="controle-ws1",
            created_by=self.owner,
            space=self.space,
        )
        ScannerAssignment.objects.create(
            activity=activity,
            agent=self.member,
            label="Responsabilité terrain",
        )
        grant_platform_role(
            profile=self.platform,
            role=SystemRoleCode.PLATFORM_ADMIN,
            granted_by=self.platform,
        )

        for actor in (self.member, self.platform):
            self.client.force_login(actor)
            self.assertEqual(self.client.get(self.space_url()).status_code, 404)

    def test_activity_scoped_authority_opens_only_the_same_space_context(self):
        scoped = User.objects.create_user(
            username="ws1-scoped", email="ws1-scoped@test.local", password="x"
        )
        activity = Activity.objects.create(
            title="Départ limité",
            slug="depart-limite",
            created_by=self.owner,
            space=self.space,
        )
        grant_activity_role(
            profile=scoped,
            activity=activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner,
        )
        other = Organization.objects.create(
            name="Space étranger", slug="space-etranger", created_by=self.owner
        )

        self.client.force_login(scoped)
        response = self.client.get(self.space_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["space_workspace"]["authority"]["scope"], "activity_limited")
        self.assertNotIn("team_summary", response.context["space_workspace"])
        self.assertEqual(
            self.client.get(
                reverse("organizations:console-entry", kwargs={"slug": other.slug})
            ).status_code,
            404,
        )

    def test_space_shell_does_not_render_sensitive_authority_material(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.space_url())
        self.assertEqual(response.status_code, 200)
        html = response.content.decode().lower()
        for forbidden in (
            "accesscredential",
            "providercredential",
            "private key",
            "api token",
            "qr token",
        ):
            self.assertNotIn(forbidden, html)
