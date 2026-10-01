from django.contrib.auth import get_user_model
from django.test import TestCase

from geography.models import Place
from organizations.models import SpaceArchetype
from organizations.services import create_organization

from .models import TransportRoute, Vehicle
from .services import create_transport_route, create_transport_vehicle


User = get_user_model()


class TransportAcrossSpaceArchetypesTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="transport-archetype-owner",
            email="transport-archetype-owner@makolo.test",
            password="TransportArchetype-2026!",
        )
        self.origin = Place.objects.create(
            name="Lubumbashi",
            locality="Lubumbashi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
        )
        self.destination = Place.objects.create(
            name="Kolwezi",
            locality="Kolwezi",
            country_code="CD",
            timezone="Africa/Lubumbashi",
        )

    def test_transport_is_not_whitelisted_by_space_archetype(self):
        archetypes = (
            SpaceArchetype.GENERIC,
            SpaceArchetype.EDUCATION,
            SpaceArchetype.COMMERCE,
            SpaceArchetype.SERVICE_PROVIDER,
            SpaceArchetype.TRANSPORT_OPERATOR,
        )
        for index, archetype in enumerate(archetypes, start=1):
            with self.subTest(archetype=archetype):
                space = create_organization(
                    creator=self.owner,
                    name=f"Espace transport {index}",
                    archetype=archetype,
                )
                route = create_transport_route(
                    space=space,
                    name="Lubumbashi → Kolwezi",
                    stops=[self.origin, self.destination],
                )
                vehicle = create_transport_vehicle(
                    space=space,
                    label=f"Bus {index}",
                    passenger_capacity=40,
                )
                self.assertEqual(route.space, space)
                self.assertEqual(vehicle.space, space)

    def test_changing_archetype_preserves_existing_transport_facts(self):
        space = create_organization(
            creator=self.owner,
            name="Espace multi-activité",
            archetype=SpaceArchetype.GENERIC,
        )
        route = create_transport_route(
            space=space,
            name="Lubumbashi → Kolwezi",
            stops=[self.origin, self.destination],
        )
        vehicle = create_transport_vehicle(
            space=space,
            label="Bus 1",
            passenger_capacity=40,
        )

        space.archetype = SpaceArchetype.COMMUNITY
        space.save()
        space.refresh_from_db()

        self.assertEqual(space.archetype, SpaceArchetype.COMMUNITY)
        self.assertTrue(TransportRoute.objects.filter(pk=route.pk, space=space).exists())
        self.assertTrue(Vehicle.objects.filter(pk=vehicle.pk, space=space).exists())
