from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.platform_services import grant_platform_role
from authorization.services import grant_activity_role, grant_space_role
from commerce.models import Offer, OfferStatus
from groups.models import Group, GroupMembership
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization, SpaceArchetype, Team, TeamMembership, TeamMembershipStatus
from scanner.models import ScannerAssignment
from services.models import ServiceDetails, ServiceKind
from transport.models import TransportRoute, Vehicle


class ZS3SpaceWorkProjectionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="zs3-owner", email="zs3-owner@test.local", password="x"
        )
        self.outsider = User.objects.create_user(
            username="zs3-outsider", email="zs3-outsider@test.local", password="x"
        )
        self.member = User.objects.create_user(
            username="zs3-member", email="zs3-member@test.local", password="x"
        )
        self.platform = User.objects.create_user(
            username="zs3-platform", email="zs3-platform@test.local", password="x"
        )
        self.space = Organization.objects.create(
            name="ZS3 Space",
            slug="zs3-space",
            created_by=self.owner,
        )
        grant_space_role(
            profile=self.owner,
            space=self.space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.owner,
        )
        team = Team.objects.create(
            organization=self.space,
            name="Equipe ZS3",
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
        self.url = "/api/v1/organizations/workspaces/zs3-space/work/"

    def _activity(self, title="Activité ZS3", **kwargs):
        return Activity.objects.create(
            title=title,
            created_by=self.owner,
            space=self.space,
            **kwargs,
        )

    def test_auth_and_minimal_disclosure_boundaries(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

        self.client.force_authenticate(self.outsider)
        self.assertEqual(self.client.get(self.url).status_code, 404)

        self.client.force_authenticate(self.member)
        self.assertEqual(self.client.get(self.url).status_code, 404)

        activity = self._activity("Scanner assignment only")
        ScannerAssignment.objects.create(
            activity=activity,
            agent=self.member,
            assigned_by=self.owner,
            label="Porte ZS3",
        )
        self.assertEqual(self.client.get(self.url).status_code, 404)

        group = Group.objects.create(
            name="Groupe ZS3",
            space=self.space,
            created_by=self.owner,
        )
        GroupMembership.objects.create(group=group, profile=self.member)
        self.assertEqual(self.client.get(self.url).status_code, 404)

        self.client.force_authenticate(self.platform)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_empty_collections_are_valid_and_do_not_invent_work(self):
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        for key in ("preparation", "upcoming", "active", "blocked", "completed"):
            self.assertEqual(response.data["sections"][key]["items"], [])
            self.assertFalse(response.data["sections"][key]["has_more"])

    def test_all_archetypes_use_zs1_business_language(self):
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
        self.client.force_authenticate(self.owner)
        for archetype, label in expected.items():
            self.space.archetype = archetype
            self.space.save(update_fields=["archetype", "updated_at"])
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200, response.data)
            self.assertEqual(response.data["primary_business_label"], label)

    def test_activity_occurrence_projection_preserves_owner_identity(self):
        activity = self._activity("Atelier")
        now = timezone.now()
        occurrence = Occurrence.objects.create(
            activity=activity,
            label="Atelier demain",
            start_at=now + timedelta(days=1),
            status=OccurrenceStatus.SCHEDULED,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        items = response.data["sections"]["upcoming"]["items"]
        row = next(item for item in items if item["source"]["id"] == str(occurrence.pk))
        self.assertEqual(row["source"], {"kind": "occurrence", "id": str(occurrence.pk)})
        self.assertEqual(row["links"]["detail"], f"/api/v1/occurrences/{occurrence.pk}/")
        self.assertEqual(row["links"]["activity"], f"/api/v1/activities/{activity.pk}/")

    def test_activity_only_authority_is_bounded_and_responsibility_cannot_expand_it(self):
        allowed = self._activity("Activity autorisée")
        hidden = self._activity("Activity cachée")
        actor = User.objects.create_user(
            username="zs3-activity", email="zs3-activity@test.local", password="x"
        )
        mandate = grant_activity_role(
            profile=actor,
            activity=allowed,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        other_mandate = grant_activity_role(
            profile=self.outsider,
            activity=hidden,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_authenticate(actor)

        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["authority"]["scope"], "activity_limited")
        serialized = str(response.data)
        self.assertIn(str(allowed.pk), serialized)
        self.assertNotIn(str(hidden.pk), serialized)
        self.assertEqual(response.data["operational_footprint"]["signals"], [])

        scoped = self.client.get(self.url, {"responsibility": f"mandate:{mandate.pk}"})
        self.assertEqual(scoped.status_code, 200, scoped.data)
        self.assertIn(str(allowed.pk), str(scoped.data))
        self.assertNotIn(str(hidden.pk), str(scoped.data))

        foreign = self.client.get(
            self.url, {"responsibility": f"mandate:{other_mandate.pk}"}
        )
        self.assertEqual(foreign.status_code, 404)

    def test_commerce_offer_requires_activity_commerce_authority(self):
        self.space.archetype = SpaceArchetype.COMMERCE
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self._activity("Catalogue")
        Offer.objects.create(
            activity=activity,
            name="Offre ZS3",
            status=OfferStatus.ACTIVE,
        )
        commerce_actor = User.objects.create_user(
            username="zs3-commerce", email="zs3-commerce@test.local", password="x"
        )
        grant_activity_role(
            profile=commerce_actor,
            activity=activity,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_authenticate(commerce_actor)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        offers = [
            item for item in response.data["sections"]["offers"]["items"]
            if item["source"]["kind"] == "offer"
        ]
        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0]["title"], "Offre ZS3")
        self.assertNotIn("payment", str(offers[0]).lower())

    def test_education_journey_is_visible_without_beneficiary_leak(self):
        self.space.archetype = SpaceArchetype.EDUCATION
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self._activity("Programme Comptabilité")
        beneficiary = User.objects.create_user(
            username="zs3-student", email="private-student@test.local", password="x"
        )
        journey = Journey.objects.create(
            initiated_by=beneficiary,
            beneficiary=beneficiary,
            activity=activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.IN_PROGRESS,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        row = next(
            item for item in response.data["sections"]["active"]["items"]
            if item["source"] == {"kind": "journey", "id": str(journey.pk)}
        )
        self.assertEqual(row["continuity_facet"]["identity"], f"journey:{journey.pk}")
        self.assertNotIn(beneficiary.email, str(row))
        self.assertNotIn(beneficiary.username, str(row))

    def test_service_case_uses_service_visibility_and_omits_private_case_data(self):
        self.space.archetype = SpaceArchetype.SERVICE_PROVIDER
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self._activity("Prestation Visa")
        ServiceDetails.objects.create(activity=activity, service_kind=ServiceKind.ADMINISTRATIVE_SUPPORT)
        beneficiary = User.objects.create_user(
            username="zs3-client", email="private-client@test.local", password="x"
        )
        journey = Journey.objects.create(
            initiated_by=beneficiary,
            beneficiary=beneficiary,
            activity=activity,
            workflow=WorkflowKind.SERVICE,
            status=JourneyStatus.IN_PROGRESS,
        )
        operator = User.objects.create_user(
            username="zs3-service", email="zs3-service@test.local", password="x"
        )
        grant_activity_role(
            profile=operator,
            activity=activity,
            role_code=SystemRoleCode.ACTIVITY_SERVICE_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_authenticate(operator)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        row = next(
            item for item in response.data["sections"]["active"]["items"]
            if item["source"] == {"kind": "journey", "id": str(journey.pk)}
        )
        self.assertEqual(row["kind"], "service_case")
        self.assertNotIn(beneficiary.email, str(row))
        self.assertNotIn("requirement", str(row).lower())

    def test_transport_space_projection_uses_real_route_and_vehicle_owners(self):
        self.space.archetype = SpaceArchetype.TRANSPORT_OPERATOR
        self.space.save(update_fields=["archetype", "updated_at"])
        route = TransportRoute.objects.create(
            space=self.space,
            name="Lubumbashi → Kolwezi",
        )
        vehicle = Vehicle.objects.create(
            space=self.space,
            label="Bus 12",
            passenger_capacity=54,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["sections"]["routes"]["role"], "structure")
        self.assertEqual(response.data["sections"]["vehicles"]["role"], "structure")
        sources = {
            (item["source"]["kind"], item["source"]["id"])
            for key in ("routes", "vehicles")
            for item in response.data["sections"][key]["items"]
        }
        self.assertIn(("transport_route", str(route.pk)), sources)
        self.assertIn(("vehicle", str(vehicle.pk)), sources)
        self.assertNotIn(("transport_route", str(route.pk)), {
            (item["source"]["kind"], item["source"]["id"])
            for item in response.data["sections"]["active"]["items"]
        })
        self.assertNotIn("scanner", str(response.data["capabilities"]).lower())
