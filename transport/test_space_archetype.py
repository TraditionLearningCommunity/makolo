from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from geography.models import Place
from organizations.models import SpaceArchetype
from organizations.services import create_organization

from .models import TransportRoute, Vehicle
from .services import create_transport_route, create_transport_vehicle


User = get_user_model()


class TransportSpaceArchetypeTests(TestCase):
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

    def test_generic_space_cannot_create_transport_primitives(self):
        space = create_organization(
            creator=self.owner,
            name="Espace générique",
            archetype=SpaceArchetype.GENERIC,
        )
        with self.assertRaisesMessage(
            ValidationError,
            "Cet Espace n’est pas configuré comme opérateur de transport.",
        ):
            TransportRoute.objects.create(space=space, name="Direct ORM")

        with self.assertRaisesMessage(
            ValidationError,
            "Cet Espace n’est pas configuré comme opérateur de transport.",
        ):
            Vehicle.objects.create(space=space, label="Direct ORM", passenger_capacity=12)

        with self.assertRaisesMessage(
            ValidationError,
            "Cet Espace n’est pas configuré comme opérateur de transport.",
        ):
            create_transport_route(
                space=space,
                name="Lubumbashi → Kolwezi",
                stops=[self.origin, self.destination],
            )
        with self.assertRaisesMessage(
            ValidationError,
            "Cet Espace n’est pas configuré comme opérateur de transport.",
        ):
            create_transport_vehicle(
                space=space,
                label="Bus 1",
                passenger_capacity=40,
            )

    def test_transport_operator_can_create_transport_primitives(self):
        space = create_organization(
            creator=self.owner,
            name="Kivu Transit",
            archetype=SpaceArchetype.TRANSPORT_OPERATOR,
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
        self.assertEqual(route.space, space)
        self.assertEqual(vehicle.space, space)