from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import grant_activity_role, grant_space_role
from organizations.models import Organization, Team, TeamMembership, TeamMembershipStatus
from organizations.space_web_views import SpaceNowView, space_projection_ui_state


def _broken_now_projection(**kwargs):
    raise RuntimeError("projection unavailable")


class WS2SpaceNowDiscoverWebTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="ws2-owner", email="ws2-owner@test.local", password="x"
        )
        self.space = Organization.objects.create(
            name="WS2 Space",
            slug="ws2-space",
            created_by=self.owner,
        )
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )

    def web_url(self, name="organizations:console-entry", **query):
        url = reverse(name, kwargs={"slug": self.space.slug})
        if not query:
            return url
        from urllib.parse import urlencode

        return f"{url}?{urlencode(query)}"

    def api_url(self, suffix, **query):
        url = f"/api/v1/organizations/workspaces/{self.space.slug}/{suffix}/"
        if not query:
            return url
        from urllib.parse import urlencode

        return f"{url}?{urlencode(query)}"

    def test_current_runtime_renders_unavailable_without_claiming_empty(self):
        self.client.force_login(self.owner)

        now = self.client.get(self.web_url())
        self.assertEqual(now.status_code, 200)
        self.assertEqual(now.context["projection_state"], "unavailable")
        self.assertContains(now, "La sélection n’est pas encore disponible.")
        self.assertNotContains(now, "Tout est en ordre. ✓")
        self.assertNotContains(now, "no_safe_selection_contract")

        discover = self.client.get(self.web_url("organizations:space-discover"))
        self.assertEqual(discover.status_code, 200)
        self.assertEqual(discover.context["projection_state"], "unavailable")
        self.assertContains(discover, "La sélection n’est pas encore disponible.")
        self.assertNotContains(discover, "no_safe_selection_contract")
        self.assertContains(discover, "Aucun candidat personnel, populaire ou récent n’est injecté")

    def test_projection_state_mapping_keeps_empty_unavailable_partial_and_error_distinct(self):
        self.assertEqual(
            space_projection_ui_state(
                {"selection": {"state": "empty"}, "items": [], "has_more": False}
            ),
            "empty",
        )
        self.assertEqual(
            space_projection_ui_state(
                {"selection": {"state": "unavailable"}, "items": [], "has_more": False}
            ),
            "unavailable",
        )
        self.assertEqual(
            space_projection_ui_state(
                {"selection": {"state": "partial"}, "items": [], "has_more": False}
            ),
            "partial",
        )
        self.assertEqual(
            space_projection_ui_state(
                {"selection": {"state": "error"}, "items": [], "has_more": False}
            ),
            "error",
        )
        self.assertEqual(space_projection_ui_state(None), "error")

    def test_valid_responsibility_is_revalidated_for_now_and_discover_web_and_api(self):
        activity = Activity.objects.create(
            title="WS2 Activity",
            slug="ws2-activity",
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

        for name in ("organizations:console-entry", "organizations:space-discover"):
            response = self.client.get(self.web_url(name, responsibility=key))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["projection"]["responsibility"], key)

        for suffix in ("now", "discover"):
            response = self.client.get(self.api_url(suffix, responsibility=key))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["responsibility"], key)

    def test_invalid_responsibility_is_privacy_safe_on_both_surfaces(self):
        self.client.force_login(self.owner)
        for name in ("organizations:console-entry", "organizations:space-discover"):
            response = self.client.get(
                self.web_url(name, responsibility="mandate:00000000-0000-0000-0000-000000000000")
            )
            self.assertEqual(response.status_code, 404)

        for suffix in ("now", "discover"):
            response = self.client.get(
                self.api_url(
                    suffix,
                    responsibility="mandate:00000000-0000-0000-0000-000000000000",
                )
            )
            self.assertEqual(response.status_code, 404)

    def test_visitor_outsider_team_member_and_platform_only_do_not_gain_space_authority(self):
        visitor = self.client.get(self.web_url())
        self.assertEqual(visitor.status_code, 302)

        outsider = User.objects.create_user(
            username="ws2-outsider", email="ws2-outsider@test.local", password="x"
        )
        team_member = User.objects.create_user(
            username="ws2-team", email="ws2-team@test.local", password="x"
        )
        platform = User.objects.create_user(
            username="ws2-platform", email="ws2-platform@test.local", password="x"
        )
        team = Team.objects.create(
            organization=self.space,
            name="WS2 Team",
            is_default=True,
            is_active=True,
        )
        TeamMembership.objects.create(
            team=team,
            user=team_member,
            status=TeamMembershipStatus.ACTIVE,
        )
        grant_platform_role(
            profile=platform,
            role=SystemRoleCode.PLATFORM_ADMIN,
            granted_by=platform,
        )

        for actor in (outsider, team_member, platform):
            self.client.force_login(actor)
            self.assertEqual(self.client.get(self.web_url()).status_code, 404)
            self.assertEqual(
                self.client.get(self.web_url("organizations:space-discover")).status_code,
                404,
            )

    def test_projection_failure_is_not_disguised_as_empty(self):
        self.client.force_login(self.owner)
        with patch.object(
            SpaceNowView,
            "projection_builder",
            new=staticmethod(_broken_now_projection),
        ):
            response = self.client.get(self.web_url())

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.context["projection_state"], "error")
        self.assertContains(response, "Maintenant n’a pas pu être chargé.", status_code=503)
        self.assertNotContains(response, "Tout est en ordre. ✓", status_code=503)

    def test_space_surfaces_do_not_render_sensitive_or_personal_discovery_material(self):
        self.client.force_login(self.owner)
        for name in ("organizations:console-entry", "organizations:space-discover"):
            response = self.client.get(self.web_url(name))
            html = response.content.decode().lower()
            for forbidden in (
                "accesscredential",
                "providercredential",
                "private key",
                "api token",
                "qr token",
                "tendances",
                "popularité",
            ):
                self.assertNotIn(forbidden, html)

        personal = self.client.get(reverse("discovery:home"))
        self.assertNotEqual(personal.status_code, 404)
