from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import grant_activity_role, grant_space_role
from crm.models import CRMContact
from groups.models import Group
from organizations.models import (
    Organization,
    SpaceArchetype,
    Team,
    TeamMembership,
    TeamMembershipStatus,
)
from partners.models import Partner


class WS4SpaceWebTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="ws4-owner", email="ws4-owner@test.local", password="x"
        )
        self.member = User.objects.create_user(
            username="ws4-member", email="ws4-member@test.local", password="x"
        )
        self.space = Organization.objects.create(
            name="WS4 Mulykap",
            slug="ws4-mulykap",
            archetype=SpaceArchetype.COMMERCE,
            description="Transport et services collectifs.",
            created_by=self.owner,
        )
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        self.team = Team.objects.create(
            organization=self.space,
            name="Équipe principale",
            is_default=True,
            is_active=True,
        )
        TeamMembership.objects.create(
            team=self.team,
            user=self.owner,
            status=TeamMembershipStatus.ACTIVE,
        )
        TeamMembership.objects.create(
            team=self.team,
            user=self.member,
            status=TeamMembershipStatus.ACTIVE,
        )

    def url(self, name, space=None, **query):
        target = space or self.space
        url = reverse(name, kwargs={"slug": target.slug})
        if query:
            from urllib.parse import urlencode

            return f"{url}?{urlencode(query)}"
        return url

    def test_us_is_collective_first_and_settings_remains_secondary(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url("organizations:space-us"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Qui sommes-nous, avec qui fonctionnons-nous et comment sommes-nous organisés ?",
        )
        self.assertContains(response, self.space.name)
        self.assertContains(response, "Équipe")
        self.assertContains(response, "Responsabilités")
        self.assertContains(response, "Ownership")
        self.assertContains(response, "Faits de vérification")
        self.assertContains(response, "Personnes & relations")
        self.assertContains(response, "Paramètres de l’Espace")
        self.assertEqual(
            response.context["projection"]["handoffs"]["team"],
            f"/space/{self.space.slug}/us/team",
        )
        html = response.content.decode().lower()
        self.assertNotIn("permissions", html)
        self.assertNotIn("health score", html)
        self.assertNotIn("performance score", html)

    def test_membership_platform_and_cross_space_access_do_not_open_ws4(self):
        platform = User.objects.create_user(
            username="ws4-platform", email="ws4-platform@test.local", password="x"
        )
        grant_platform_role(
            profile=platform,
            role=SystemRoleCode.PLATFORM_ADMIN,
            granted_by=platform,
        )
        other = Organization.objects.create(
            name="WS4 étranger",
            slug="ws4-etranger",
            created_by=self.owner,
        )

        for actor in (self.member, platform):
            self.client.force_login(actor)
            for route in (
                "organizations:space-us",
                "organizations:space-relationships",
                "organizations:space-pilot",
            ):
                self.assertEqual(self.client.get(self.url(route)).status_code, 404)

        self.client.force_login(self.owner)
        self.assertEqual(
            self.client.get(self.url("organizations:space-us", space=other)).status_code,
            404,
        )

    def test_activity_scoped_authority_stays_minimal_on_relations_and_pilot(self):
        scoped = User.objects.create_user(
            username="ws4-scoped", email="ws4-scoped@test.local", password="x"
        )
        activity = Activity.objects.create(
            title="Départ WS4",
            slug="depart-ws4",
            created_by=self.owner,
            space=self.space,
        )
        grant_activity_role(
            profile=scoped,
            activity=activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_login(scoped)

        us = self.client.get(self.url("organizations:space-us"))
        self.assertEqual(us.status_code, 200)
        self.assertEqual(us.context["projection"]["authority"]["scope"], "activity_limited")
        self.assertNotIn("relationships", us.context["projection"]["handoffs"])
        self.assertNotIn("team", us.context["projection"]["handoffs"])
        self.assertNotContains(us, self.member.full_name or self.member.username)

        relationships = self.client.get(self.url("organizations:space-relationships"))
        self.assertEqual(relationships.status_code, 200)
        self.assertContains(
            relationships,
            "Relations globales indisponibles dans cette responsabilité",
        )

        pilot = self.client.get(self.url("organizations:space-pilot"))
        self.assertEqual(pilot.status_code, 200)
        self.assertContains(
            pilot,
            "Pilotage global indisponible pour cette responsabilité",
        )

    def test_relationships_preserve_kinds_and_same_profile_is_not_merged(self):
        Group.objects.create(
            name="Clients premium",
            slug="clients-premium-ws4",
            space=self.space,
            created_by=self.owner,
        )
        CRMContact.objects.create(
            organization=self.space,
            user=self.member,
            email=self.member.email,
            phone="+243000000000",
            name="Marie CRM",
        )
        Partner.objects.create(
            organization=self.space,
            user=self.member,
            name="Marie partenaire",
            created_by=self.owner,
        )

        self.client.force_login(self.owner)
        response = self.client.get(self.url("organizations:space-relationships"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Collaborateur · Équipe")
        self.assertContains(response, "Contact CRM")
        self.assertContains(response, "Partenaire")
        self.assertContains(response, self.member.full_name or self.member.username)
        html = response.content.decode()
        self.assertNotIn(self.member.email, html)
        self.assertNotIn("+243000000000", html)

    def test_relationship_preview_keeps_server_bound_and_known_empty_sections(self):
        for index in range(13):
            CRMContact.objects.create(
                organization=self.space,
                name=f"Contact borné {index:02d}",
                email=f"bounded-{index}@test.local",
            )

        self.client.force_login(self.owner)
        response = self.client.get(self.url("organizations:space-relationships"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Aperçu limité à 12 relations.")
        self.assertContains(response, "Contact borné 00")
        self.assertNotContains(response, "Contact borné 12")
        self.assertContains(response, "Aucun groupe visible dans ce contexte.")

    def test_pilot_preserves_zero_and_insufficient_data_without_score(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url("organizations:space-pilot"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            "Pas encore assez d’activité pour dégager une tendance utile.",
        )
        self.assertContains(response, "Événements")
        events = next(
            row
            for row in response.context["projection"]["sections"]["analytics"]["metrics"]
            if row["key"] == "events_count"
        )
        self.assertEqual(events["state"], "known")
        self.assertEqual(events["value"], 0)
        self.assertContains(response, "<strong>0</strong>", html=True)
        self.assertContains(response, "Données insuffisantes")
        self.assertContains(response, "événements visibles max.")
        html = response.content.decode().lower()
        self.assertNotIn("health score", html)
        self.assertNotIn("performance score", html)
        self.assertNotIn("space score", html)

    def test_pilot_renders_unknown_unavailable_and_insufficient_as_distinct_states(self):
        projection = {
            "authority": {"scope": "space", "limited_to_activities": False},
            "sections": {
                "analytics": {
                    "state": "known",
                    "metrics": [
                        {"key": "known_zero", "state": "known", "value": 0, "unit": "count"},
                        {"key": "unknown_value", "state": "unknown", "value": None, "unit": "count"},
                        {"key": "unavailable_value", "state": "unavailable", "value": None, "unit": "count"},
                        {"key": "thin_value", "state": "insufficient_data", "value": None, "unit": "percent"},
                    ],
                    "money": [],
                    "signals": [],
                    "coverage": {"kind": "test", "limit": 40},
                    "links": {},
                }
            },
            "signals": [],
            "links": {},
            "capabilities": {"view_analytics": True, "view_financials": False},
        }
        self.client.force_login(self.owner)
        with patch(
            "organizations.space_web_views.build_space_pilot_projection",
            return_value=projection,
        ):
            response = self.client.get(self.url("organizations:space-pilot"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Inconnu")
        self.assertContains(response, "Indisponible")
        self.assertContains(response, "Données insuffisantes")
        self.assertContains(response, "<strong>0</strong>", html=True)

    def test_foreign_responsibility_never_falls_back_on_ws4_routes(self):
        foreign_space = Organization.objects.create(
            name="Responsabilité étrangère",
            slug="responsabilite-etrangere-ws4",
            created_by=self.owner,
        )
        foreign = grant_space_role(
            profile=self.owner,
            space=foreign_space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )

        self.client.force_login(self.owner)
        for route in (
            "organizations:space-us",
            "organizations:space-relationships",
            "organizations:space-pilot",
        ):
            response = self.client.get(
                self.url(route, responsibility=f"mandate:{foreign.pk}")
            )
            self.assertEqual(response.status_code, 404)

    def test_transverse_retrieval_is_secondary_and_authority_scoped(self):
        from datetime import timedelta
        from django.utils import timezone
        from activities.models import Occurrence, OccurrenceStatus
        past = Occurrence.objects.create(
            activity=Activity.objects.create(
                title="Atelier de mémoire", created_by=self.owner, space=self.space,
            ),
            label="Session achevée",
            status=OccurrenceStatus.COMPLETED,
            start_at=timezone.now() - timedelta(days=2),
            end_at=timezone.now() - timedelta(days=1),
        )
        self.client.force_login(self.owner)
        history = self.client.get(self.url("organizations:space-history"))
        self.assertEqual(history.status_code, 200)
        self.assertContains(history, "Session achevée")
        self.assertContains(history, "Couverture partielle")
        search = self.client.get(
            self.url("organizations:space-search", q="Atelier")
        )
        self.assertEqual(search.status_code, 200)
        self.assertContains(search, "Atelier de mémoire")
        self.client.force_login(self.member)
        self.assertEqual(
            self.client.get(self.url("organizations:space-history")).status_code, 404
        )
        self.assertEqual(
            self.client.get(self.url("organizations:space-search")).status_code, 404
        )
