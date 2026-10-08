from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import grant_activity_role, grant_space_role, revoke_mandate
from journeys.collaboration_models import JourneyBlocker, JourneyBlockerStatus
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization, SpaceArchetype, Team, TeamMembership, TeamMembershipStatus
from services.models import ServiceDetails, ServiceKind
from transport.models import TransportRoute, Vehicle


class WS3SpaceWorkWebTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="ws3-owner", email="ws3-owner@test.local", password="x"
        )
        self.member = User.objects.create_user(
            username="ws3-member", email="ws3-member@test.local", password="x"
        )
        self.platform = User.objects.create_user(
            username="ws3-platform", email="ws3-platform@test.local", password="x"
        )
        self.space = Organization.objects.create(
            name="WS3 Académie",
            slug="ws3-academie",
            archetype=SpaceArchetype.EDUCATION,
            created_by=self.owner,
        )
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        self.url = reverse("organizations:space-work", kwargs={"slug": self.space.slug})

    def _activity(self, title, status=ActivityStatus.DRAFT):
        return Activity.objects.create(
            title=title,
            created_by=self.owner,
            space=self.space,
            status=status,
        )

    def test_authority_boundaries_are_privacy_safe(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

        outsider = User.objects.create_user(
            username="ws3-outsider", email="ws3-outsider@test.local", password="x"
        )
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(self.url).status_code, 404)

        team = Team.objects.create(
            organization=self.space,
            name="Equipe WS3",
            is_active=True,
        )
        TeamMembership.objects.create(
            team=team,
            user=self.member,
            status=TeamMembershipStatus.ACTIVE,
        )
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(self.url).status_code, 404)

        grant_platform_role(
            profile=self.platform,
            role=SystemRoleCode.PLATFORM_ADMIN,
            granted_by=self.platform,
        )
        self.client.force_login(self.platform)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_archetype_language_is_consumed_from_server_projection(self):
        expected = {
            SpaceArchetype.GENERIC: "Activités",
            SpaceArchetype.CREATIVE: "Créations",
            SpaceArchetype.MEDIA: "Productions",
            SpaceArchetype.EDUCATION: "Programmes",
            SpaceArchetype.COMMERCE: "Commerce",
            SpaceArchetype.SERVICE_PROVIDER: "Prestations",
            SpaceArchetype.TRANSPORT_OPERATOR: "Transport",
            SpaceArchetype.COMMUNITY: "Initiatives",
        }
        self.client.force_login(self.owner)
        for archetype, label in expected.items():
            self.space.archetype = archetype
            self.space.save(update_fields=["archetype", "updated_at"])
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["projection"]["primary_business_label"], label)
            self.assertContains(response, f">{label}<")

    def test_sections_are_projection_backed_and_empty_is_honest(self):
        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["work_has_items"])
        self.assertContains(response, "Aucun programme ou session visible pour le moment.")
        self.assertContains(response, "Makolo n’invente pas d’activité")
        self.assertNotContains(response, 'id="work-preparation"')
        self.assertNotContains(response, 'id="work-upcoming"')
        self.assertNotContains(response, 'id="work-active"')
        self.assertNotContains(response, 'id="work-blocked"')
        self.assertNotContains(response, 'id="work-completed"')

    def test_activity_and_occurrence_render_in_server_selected_sections(self):
        draft = self._activity("Programme à préparer", ActivityStatus.DRAFT)
        published = self._activity("Programme actif", ActivityStatus.PUBLISHED)
        occurrence = Occurrence.objects.create(
            activity=published,
            label="Session de demain",
            start_at=timezone.now() + timedelta(days=1),
            status=OccurrenceStatus.SCHEDULED,
        )

        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)

        sections = {section["key"]: section for section in response.context["work_sections"]}
        self.assertTrue(any(item["source"]["id"] == str(draft.pk) for item in sections["preparation"]["items"]))
        self.assertTrue(any(item["source"]["id"] == str(published.pk) for item in sections["activities"]["items"]))
        self.assertTrue(any(item["source"]["id"] == str(occurrence.pk) for item in sections["upcoming"]["items"]))
        self.assertContains(response, "Session de demain")

    def test_blocked_is_only_rendered_from_real_zs3_blocker(self):
        activity = self._activity("Prestation dossier", ActivityStatus.PUBLISHED)
        ServiceDetails.objects.create(
            activity=activity,
            service_kind=ServiceKind.ADMINISTRATIVE_SUPPORT,
        )
        beneficiary = User.objects.create_user(
            username="ws3-beneficiary", email="private-ws3@test.local", password="x"
        )
        journey = Journey.objects.create(
            initiated_by=beneficiary,
            beneficiary=beneficiary,
            activity=activity,
            workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.IN_PROGRESS,
        )
        JourneyBlocker.objects.create(
            journey=journey,
            title="Pièce indispensable",
            status=JourneyBlockerStatus.ACTIVE,
        )

        operator = User.objects.create_user(
            username="ws3-service-operator",
            email="ws3-service-operator@test.local",
            password="x",
        )
        grant_activity_role(
            profile=operator,
            activity=activity,
            role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
            granted_by=self.owner,
        )

        self.client.force_login(operator)
        response = self.client.get(self.url)
        sections = {section["key"]: section for section in response.context["work_sections"]}
        self.assertTrue(
            any(item["source"] == {"kind": "journey", "id": str(journey.pk)} for item in sections["blocked"]["items"])
        )
        self.assertNotContains(response, beneficiary.email)
        self.assertNotContains(response, "Pièce indispensable")

    def test_owner_handoff_exists_only_when_projection_exposes_activity_owner(self):
        activity = self._activity("Programme owner-backed", ActivityStatus.PUBLISHED)
        self.space.archetype = SpaceArchetype.TRANSPORT_OPERATOR
        self.space.save(update_fields=["archetype", "updated_at"])
        route = TransportRoute.objects.create(space=self.space, name="Lubumbashi → Kolwezi")
        vehicle = Vehicle.objects.create(space=self.space, label="Bus WS3", passenger_capacity=42)

        self.client.force_login(self.owner)
        response = self.client.get(self.url)
        sections = {section["key"]: section for section in response.context["work_sections"]}
        activity_item = next(item for item in sections["activities"]["items"] if item["source"]["id"] == str(activity.pk))
        route_item = next(item for item in sections["routes"]["items"] if item["source"]["id"] == str(route.pk))
        vehicle_item = next(item for item in sections["vehicles"]["items"] if item["source"]["id"] == str(vehicle.pk))

        self.assertEqual(
            activity_item["owner_url"],
            reverse(
                "organizations:console-activity-detail",
                kwargs={"slug": self.space.slug, "activity_id": activity.pk},
            ),
        )
        self.assertIsNone(route_item["owner_url"])
        self.assertIsNone(vehicle_item["owner_url"])

    def test_responsibility_filters_reading_and_foreign_or_revoked_keys_are_404(self):
        allowed = self._activity("Programme autorisé", ActivityStatus.PUBLISHED)
        hidden = self._activity("Programme caché", ActivityStatus.PUBLISHED)
        actor = User.objects.create_user(
            username="ws3-scoped", email="ws3-scoped@test.local", password="x"
        )
        mandate = grant_activity_role(
            profile=actor,
            activity=allowed,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        foreign_actor = User.objects.create_user(
            username="ws3-foreign", email="ws3-foreign@test.local", password="x"
        )
        foreign_mandate = grant_activity_role(
            profile=foreign_actor,
            activity=hidden,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )

        self.client.force_login(actor)
        response = self.client.get(self.url, {"responsibility": f"mandate:{mandate.pk}"})
        self.assertEqual(response.status_code, 200)
        rendered = response.content.decode()
        self.assertIn("Programme autorisé", rendered)
        self.assertNotIn("Programme caché", rendered)

        self.assertEqual(
            self.client.get(
                self.url,
                {"responsibility": f"mandate:{foreign_mandate.pk}"},
            ).status_code,
            404,
        )

        revoke_mandate(mandate=mandate, actor=self.owner)
        self.assertEqual(
            self.client.get(
                self.url,
                {"responsibility": f"mandate:{mandate.pk}"},
            ).status_code,
            404,
        )

    def test_transport_archetype_does_not_grant_transport_portfolio(self):
        self.space.archetype = SpaceArchetype.TRANSPORT_OPERATOR
        self.space.save(update_fields=["archetype", "updated_at"])
        allowed = self._activity("Départ autorisé", ActivityStatus.PUBLISHED)
        TransportRoute.objects.create(space=self.space, name="Route privée")
        Vehicle.objects.create(space=self.space, label="Véhicule privé", passenger_capacity=12)

        actor = User.objects.create_user(
            username="ws3-activity-only", email="ws3-activity-only@test.local", password="x"
        )
        grant_activity_role(
            profile=actor,
            activity=allowed,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )

        self.client.force_login(actor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Transport")
        self.assertContains(response, "Départ autorisé")
        self.assertNotContains(response, "Route privée")
        self.assertNotContains(response, "Véhicule privé")
        self.assertContains(response, "Vue limitée à vos activités autorisées")
