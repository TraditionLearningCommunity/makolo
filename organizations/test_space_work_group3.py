"""Group 3: Commerce and Transport are owner-backed Space Work perspectives."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import User
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from capacity.models import CapacityPool
from commerce.models import CommerceOrder, CommerceOrderStatus, Offer, OfferStatus
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization, SpaceArchetype
from transport.models import TransportDeparture, TransportRoute, TransportService, Vehicle


class SpaceWorkGroup3Tests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="g3-owner", password="x")
        self.viewer = User.objects.create_user(username="g3-viewer", password="x")
        self.client_user = User.objects.create_user(
            username="g3-client", email="private-g3-buyer@test.local", password="x"
        )
        self.space = Organization.objects.create(
            name="G3 Space", slug="g3-space", created_by=self.owner
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        self.client = APIClient()
        self.url = reverse(
            "organizations_api:workspace-work", kwargs={"slug": self.space.slug}
        )
        self.web_url = reverse(
            "organizations:space-work", kwargs={"slug": self.space.slug}
        )

    def activity(self, title):
        item = Activity.objects.create(
            title=title, space=self.space, created_by=self.owner,
            status=ActivityStatus.PUBLISHED,
        )
        grant_activity_role(
            profile=self.owner, activity=item,
            role_code=SystemRoleCode.ACTIVITY_MANAGER,
            granted_by=self.owner,
        )
        return item

    def test_commerce_orders_and_offers_are_separate_owner_sections(self):
        self.space.archetype = SpaceArchetype.COMMERCE
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self.activity("Distribution de matériel")
        pool = CapacityPool.objects.create(
            activity=activity, total_quantity=12, label="Lots disponibles"
        )
        offer = Offer.objects.create(
            activity=activity, name="Kit principal",
            status=OfferStatus.ACTIVE, unit_price=Decimal("14.50"),
            capacity_pool=pool,
        )
        journey = Journey.objects.create(
            initiated_by=self.client_user, beneficiary=self.client_user,
            activity=activity, workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        order = CommerceOrder.objects.create(
            journey=journey, payee_space=self.space, buyer=self.client_user,
            status=CommerceOrderStatus.CONFIRMED,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            [group["identity"] for group in response.data["business_world"]["reading_groups"]],
            ["orders", "availability"],
        )
        self.assertEqual(
            response.data["presentation"]["section_order"],
            ["active", "offers", "activities"],
        )
        order_row = next(
            item for item in response.data["sections"]["active"]["items"]
            if item["source"]["id"] == str(order.pk)
        )
        self.assertEqual(order_row["state"], CommerceOrderStatus.CONFIRMED)
        self.assertEqual(order_row["context"]["owner_state_label"], "Confirmée")
        self.assertIn("commerce/orders/", order_row["links"]["detail"])
        self.assertNotIn("delivered", str(order_row).lower())
        offer_row = response.data["sections"]["offers"]["items"][0]
        self.assertEqual(offer_row["source"]["id"], str(offer.pk))
        self.assertEqual(offer_row["context"]["capacity"], {
            "total": 12, "available": 12, "unlimited": False,
            "sold_out": False, "pool_active": True, "basis": "capacity_pool",
        })
        self.assertNotIn(self.client_user.email, str(response.data))
        self.client.force_authenticate(self.viewer)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_commerce_durable_offer_without_order_has_calm_structure(self):
        self.space.archetype = SpaceArchetype.COMMERCE
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self.activity("Ressources disponibles")
        Offer.objects.create(
            activity=activity, name="Produit libre", status=OfferStatus.INACTIVE,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            [group["identity"] for group in response.data["business_world"]["reading_groups"]],
            ["availability"],
        )
        self.assertIn("Aucune commande",
                      response.data["presentation"]["calm_message"])
        self.assertEqual(
            response.data["sections"]["offers"]["items"][0]["state"],
            OfferStatus.INACTIVE,
        )
        self.assertNotIn(
            "capacity", response.data["sections"]["offers"]["items"][0]["context"]
        )

    def test_transport_route_vehicle_and_real_departure_keep_distinct_owners(self):
        self.space.archetype = SpaceArchetype.TRANSPORT_OPERATOR
        self.space.save(update_fields=["archetype", "updated_at"])
        route = TransportRoute.objects.create(
            space=self.space, name="Lubumbashi - Kolwezi"
        )
        vehicle = Vehicle.objects.create(
            space=self.space, label="Bus 18", passenger_capacity=40
        )
        service = self.activity("Service interurbain")
        TransportService.objects.create(activity=service, route=route)
        now = timezone.now()
        occurrence = Occurrence.objects.create(
            activity=service, label="Départ du jour",
            start_at=now - timedelta(seconds=2),
            end_at=now + timedelta(hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        pool = CapacityPool.objects.create(
            activity=service, occurrence=occurrence, total_quantity=30,
        )
        departure = TransportDeparture.objects.create(
            occurrence=occurrence, vehicle=vehicle,
            passenger_capacity_pool=pool,
        )
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(
            [group["identity"] for group in response.data["business_world"]["reading_groups"]],
            ["departures", "structure", "services"],
        )
        item = next(
            item for item in response.data["sections"]["active"]["items"]
            if item["source"]["id"] == str(occurrence.pk)
        )
        self.assertEqual(item["kind"], "departure")
        self.assertEqual(item["context"]["transport"]["departure_id"], str(departure.pk))
        self.assertEqual(item["context"]["transport"]["route"]["id"], str(route.pk))
        self.assertEqual(item["context"]["transport"]["vehicle"]["label"], "Bus 18")
        self.assertEqual(item["context"]["capacity"]["available"], 30)
        self.assertEqual(item["context"]["capacity"]["total"], 30)
        self.assertTrue(item["context"]["capacity"]["pool_active"])
        self.assertEqual(
            response.data["presentation"]["today_departures"][0]["source"]["id"],
            str(occurrence.pk),
        )
        self.assertIn("day_of", item["links"])
        self.assertIn("open_day_of", item["capabilities"])
        routes = response.data["sections"]["routes"]["items"]
        vehicles = response.data["sections"]["vehicles"]["items"]
        self.assertEqual(routes[0]["source"]["id"], str(route.pk))
        self.assertEqual(vehicles[0]["source"]["id"], str(vehicle.pk))
        self.assertEqual(vehicles[0]["state"], "active")
        self.assertNotIn("transport_route:", str(response.data["sections"]["active"]))

    def test_departure_without_assigned_vehicle_is_not_invented_blocked(self):
        self.space.archetype = SpaceArchetype.TRANSPORT_OPERATOR
        self.space.save(update_fields=["archetype", "updated_at"])
        route = TransportRoute.objects.create(
            space=self.space, name="Route ouverte"
        )
        activity = self.activity("Service en préparation")
        TransportService.objects.create(activity=activity, route=route)
        occurrence = Occurrence.objects.create(
            activity=activity, label="Départ sans affectation",
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=3),
            status=OccurrenceStatus.SCHEDULED,
        )
        pool = CapacityPool.objects.create(
            activity=activity, occurrence=occurrence, total_quantity=8,
        )
        TransportDeparture.objects.create(
            occurrence=occurrence, passenger_capacity_pool=pool
        )
        self.client.force_authenticate(self.owner)
        result = self.client.get(self.url)
        self.assertEqual(result.status_code, 200, result.data)
        departure = next(
            row for row in result.data["sections"]["upcoming"]["items"]
            if row["source"]["id"] == str(occurrence.pk)
        )
        self.assertIsNone(departure["context"]["transport"]["vehicle"])
        self.assertEqual(departure["context"]["capacity"]["available"], 8)
        self.assertNotIn("readiness", str(departure).lower())
        self.assertFalse(result.data["sections"]["blocked"]["items"])

    def test_transport_activity_mandate_does_not_reveal_space_wide_fleet(self):
        self.space.archetype = SpaceArchetype.TRANSPORT_OPERATOR
        self.space.save(update_fields=["archetype", "updated_at"])
        route = TransportRoute.objects.create(
            space=self.space, name="Route réservée au propriétaire"
        )
        Vehicle.objects.create(
            space=self.space, label="Véhicule privé", passenger_capacity=22
        )
        activity = self.activity("Service autorisé")
        grant_activity_role(
            profile=self.viewer, activity=activity,
            role_code=SystemRoleCode.ACTIVITY_MANAGER, granted_by=self.owner,
        )
        self.client.force_authenticate(self.viewer)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["business_world"]["authority_scope"],
                         "activity_limited")
        self.assertNotIn("routes", response.data["sections"])
        self.assertNotIn("vehicles", response.data["sections"])
        self.assertNotIn(route.name, str(response.data))
        self.assertNotIn("Véhicule privé", str(response.data))

    def test_web_handoffs_reuse_real_commerce_owner_destinations(self):
        self.space.archetype = SpaceArchetype.COMMERCE
        self.space.save(update_fields=["archetype", "updated_at"])
        activity = self.activity("Boutique")
        Offer.objects.create(
            activity=activity, name="Trousse disponible", status=OfferStatus.ACTIVE
        )
        journey = Journey.objects.create(
            initiated_by=self.client_user, beneficiary=self.client_user,
            activity=activity, workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        order = CommerceOrder.objects.create(
            journey=journey, payee_space=self.space,
            buyer=self.client_user, status=CommerceOrderStatus.CONFIRMED,
        )
        self.client.force_authenticate(self.owner)
        # The browser and the API share the same scoped owner projection.
        self.client.force_authenticate(None)
        self.client.force_login(self.owner)
        response = self.client.get(self.web_url)
        self.assertEqual(response.status_code, 200)
        sections = {
            section["key"]: section for section in response.context["work_sections"]
        }
        order_row = next(
            item for item in sections["active"]["items"]
            if item["source"]["id"] == str(order.pk)
        )
        self.assertEqual(order_row["owner_url"], reverse(
            "organizations:space-retrieval-order-detail",
            kwargs={"slug": self.space.slug, "order_id": order.pk},
        ))
        self.assertEqual(order_row["owner_label"], "Voir la commande")
        self.assertEqual(
            sections["offers"]["items"][0]["owner_url"],
            reverse("organizations:console-offers", kwargs={"slug": self.space.slug}),
        )
        self.assertContains(response, "Commandes et traitement")
        self.assertContains(response, "Disponibilité" if False else "Ce que nous rendons disponible")
        self.assertNotContains(response, self.client_user.email)

    def test_transport_web_routes_to_real_departure_and_route_depth(self):
        self.space.archetype = SpaceArchetype.TRANSPORT_OPERATOR
        self.space.save(update_fields=["archetype", "updated_at"])
        route = TransportRoute.objects.create(
            space=self.space, name="Route Matadi"
        )
        vehicle = Vehicle.objects.create(
            space=self.space, label="Bus Matadi", passenger_capacity=25
        )
        activity = self.activity("Service Matadi")
        TransportService.objects.create(activity=activity, route=route)
        now = timezone.now()
        occurrence = Occurrence.objects.create(
            activity=activity, label="Départ Matadi",
            start_at=now - timedelta(seconds=2),
            end_at=now + timedelta(hours=1),
            status=OccurrenceStatus.SCHEDULED,
        )
        pool = CapacityPool.objects.create(
            activity=activity, occurrence=occurrence, total_quantity=20
        )
        departure = TransportDeparture.objects.create(
            occurrence=occurrence, passenger_capacity_pool=pool, vehicle=vehicle
        )
        self.client.force_login(self.owner)
        response = self.client.get(self.web_url)
        self.assertEqual(response.status_code, 200)
        sections = {
            section["key"]: section for section in response.context["work_sections"]
        }
        active = next(
            row for row in sections["active"]["items"]
            if row["source"]["id"] == str(occurrence.pk)
        )
        self.assertEqual(
            active["owner_url"], reverse(
                "organizations:console-transport-departure-detail",
                kwargs={"slug": self.space.slug, "departure_id": departure.pk},
            ),
        )
        route_row = sections["routes"]["items"][0]
        self.assertEqual(
            route_row["owner_url"], reverse(
                "organizations:console-transport-route-detail",
                kwargs={"slug": self.space.slug, "route_id": route.pk},
            ),
        )
        vehicle_row = sections["vehicles"]["items"][0]
        self.assertEqual(
            vehicle_row["owner_url"], reverse(
                "organizations:console-transport", kwargs={"slug": self.space.slug},
            ),
        )
        self.assertContains(response, "Départs et exploitation")
        self.assertContains(response, "Aujourd’hui")
        self.assertContains(response, "Bus Matadi")
        self.assertContains(response, "Disponibilité : 20 sur 20")

    def test_transport_owner_selection_is_denied_across_spaces(self):
        self.space.archetype = SpaceArchetype.TRANSPORT_OPERATOR
        self.space.save(update_fields=["archetype", "updated_at"])
        other = Organization.objects.create(
            name="Foreign Group 3", slug="g3-foreign", created_by=self.owner
        )
        route = TransportRoute.objects.create(
            space=other, name="Foreign route",
        )
        self.client.force_authenticate(self.owner)
        result = self.client.get(
            self.url, {"kind": "transport_route", "id": str(route.pk)}
        )
        self.assertEqual(result.status_code, 200, result.data)
        self.assertIsNone(result.data["selection"])
        self.assertNotIn("Foreign route", str(result.data))

    def test_other_archetypes_do_not_inherit_group_three(self):
        self.space.archetype = SpaceArchetype.MEDIA
        self.space.save(update_fields=["archetype", "updated_at"])
        self.activity("Production reconnue")
        self.client.force_authenticate(self.owner)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertNotIn("business_world", response.data)
