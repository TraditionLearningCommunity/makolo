from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import grant_space_role
from events.models import Event, EventStatus, EventVisibility
from organizations.console_context import SpaceConsoleContext
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus


class W7OrphanCapabilityReachabilityTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="w7-owner", email="w7-owner@test.local", password="x"
        )
        self.member = User.objects.create_user(
            username="w7-member", email="w7-member@test.local", password="x"
        )
        self.platform = User.objects.create_user(
            username="w7-platform", email="w7-platform@test.local", password="x"
        )
        self.space = Organization.objects.create(
            name="W7 Space", slug="w7-space", created_by=self.owner
        )
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        team = Team.objects.create(
            organization=self.space,
            name="Equipe W7",
            is_active=True,
        )
        TeamMembership.objects.create(
            team=team,
            user=self.member,
            status=TeamMembershipStatus.ACTIVE,
        )
        grant_platform_role(
            profile=self.platform,
            role=SystemRoleCode.PLATFORM_ADMIN,
            granted_by=self.platform,
        )
        self.client = APIClient()

    def test_owner_navigation_consumes_z15_workspace_capabilities(self):
        context = SpaceConsoleContext.build(self.owner, self.space)
        self.assertIsNotNone(context)
        keys = {
            item["key"]
            for group in context.navigation_groups
            for item in group["items"]
        }
        for expected in {
            "partners",
            "growth",
            "loyalty",
            "recognition",
            "trust",
            "funding",
        }:
            self.assertIn(expected, keys)

    def test_reconciled_capabilities_have_mature_space_entry_points(self):
        self.client.force_login(self.owner)
        for path in (
            "/spaces/w7-space/partners/",
            "/spaces/w7-space/growth/",
            "/spaces/w7-space/loyalty/",
            "/spaces/w7-space/recognition/",
            "/spaces/w7-space/trust/",
            "/spaces/w7-space/funding/",
        ):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, path)
            self.assertContains(response, "W7 Space")

    def test_membership_without_mandate_does_not_gain_w7_entries(self):
        self.client.force_login(self.member)
        for path in (
            "/spaces/w7-space/partners/",
            "/spaces/w7-space/loyalty/",
            "/spaces/w7-space/trust/",
            "/spaces/w7-space/funding/",
        ):
            self.assertEqual(self.client.get(path).status_code, 403)

    def test_platform_authority_does_not_gain_space_w7_entries(self):
        self.client.force_login(self.platform)
        for path in (
            "/spaces/w7-space/partners/",
            "/spaces/w7-space/recognition/",
            "/spaces/w7-space/trust/",
        ):
            self.assertEqual(self.client.get(path).status_code, 403)

    def test_existing_space_surfaces_reach_advanced_owner_tools(self):
        start_at = timezone.now() + timedelta(hours=2)
        Event.objects.create(
            organizer=self.owner,
            organization=self.space,
            title="W7 Access Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start_at,
            end_at=start_at + timedelta(hours=3),
            published_at=timezone.now(),
        )
        self.client.force_login(self.owner)

        analytics = self.client.get("/spaces/w7-space/analytics/")
        self.assertEqual(analytics.status_code, 200)
        self.assertContains(analytics, "/analytics/growth/o/w7-space/")

        automation = self.client.get("/spaces/w7-space/automation/")
        self.assertEqual(automation.status_code, 200)
        self.assertContains(automation, "/autopilot/crm/w7-space/")

        control = self.client.get("/spaces/w7-space/control/")
        self.assertEqual(control.status_code, 200)
        self.assertContains(control, "/scanner/logs/")
        self.assertContains(control, "/scanner/gates/")
        self.assertContains(control, "/scanner/assignments/")

    def test_space_funding_create_keeps_space_preselected(self):
        self.client.force_login(self.owner)
        response = self.client.get("/funding/new/?space=w7-space")
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(form.initial["space"], self.space)
