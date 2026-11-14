"""MT5: Commerce/Transport owner depths, mutations, IDOR and source boundaries."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import SystemRoleCode
from authorization.services import (
    grant_activity_role, grant_space_role, revoke_mandate,
)
from capacity.models import CapacityPool
from commerce.models import (
    CommerceOrder, CommerceOrderItem, CommerceOrderStatus,
    Offer, OfferStatus, PaymentMode,
)
from commerce.services import set_offer_payment_modes
from geography.models import Place, SpacePlace
from journeys.models import Journey, JourneyStatus, WorkflowKind
from organizations.models import Organization, SpaceArchetype
from transport.models import (
    TransportDeparture, TransportRoute, TransportService, Vehicle,
)


class MT5CommerceTransportTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="mt5-owner", password="x",
        )
        self.outsider = User.objects.create_user(
            username="mt5-outsider", password="x",
        )
        self.buyer = User.objects.create_user(
            username="mt5-buyer", email="private-mt5@example.test",
            password="x",
        )
        self.space = Organization.objects.create(
            name="MT5 Métier", slug="mt5-space", created_by=self.owner,
            archetype=SpaceArchetype.COMMERCE,
        )
        grant_space_role(
            profile=self.owner, space=self.space,
            role=SystemRoleCode.SPACE_OWNER, granted_by=self.owner,
        )
        self.client.force_login(self.owner)
        self.work_url = reverse(
            "organizations_api:workspace-work",
            kwargs={"slug": self.space.slug},
        )

    def activity(self, title="Boutique opérationnelle"):
        item = Activity.objects.create(
            title=title, space=self.space, created_by=self.owner,
            status=ActivityStatus.PUBLISHED,
        )
        grant_activity_role(
            profile=self.owner, activity=item,
            role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner,
        )
        return item

    def offer(self, activity, name="Kit essentiel", amount="14.50"):
        return Offer.objects.create(
            activity=activity, name=name,
            status=OfferStatus.ACTIVE, unit_price=Decimal(amount),
            payment_mode=PaymentMode.UPFRONT,
        )

    def order(self, activity):
        journey = Journey.objects.create(
            initiated_by=self.buyer, beneficiary=self.buyer,
            activity=activity, workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        return CommerceOrder.objects.create(
            journey=journey, payee_space=self.space, buyer=self.buyer,
            status=CommerceOrderStatus.CONFIRMED,
            payment_mode=PaymentMode.UPFRONT,
            subtotal=Decimal("18.00"), total=Decimal("18.00"),
        )

    def order_line(self, order, offer, label="Ancien kit", quantity=2):
        return CommerceOrderItem.objects.create(
            order=order, offer=offer,
            quantity=quantity, label_snapshot=label,
            unit_price=Decimal("9.00"),
            line_subtotal=Decimal("9.00") * quantity,
            line_total=Decimal("9.00") * quantity,
        )

    def depth(self, kind, pk, **query):
        from urllib.parse import urlencode
        url = reverse(
            "organizations:space-work-depth-g3",
            kwargs={"slug": self.space.slug, "kind": kind, "owner_id": pk},
        )
        return url + ("?" + urlencode(query) if query else "")

    def selected(self, kind, pk, **query):
        return self.client.get(self.work_url, {
            "kind": kind, "id": str(pk), **query,
        })

    def test_commerce_offer_n1_to_n2_owner_price_and_true_availability(self):
        activity = self.activity()
        offer = self.offer(activity)
        root = self.client.get(reverse(
            "organizations:space-work", kwargs={"slug": self.space.slug},
        ))
        self.assertEqual(root.status_code, 200)
        items = [
            row for section in root.context["work_sections"]
            for row in section["items"]
            if row["source"] == {"kind": "offer", "id": str(offer.pk)}
        ]
        self.assertEqual(len(items), 1)
        self.assertIn("/work/g3/offer/", items[0]["owner_url"])
        self.assertEqual(items[0]["owner_label"], "Voir l’offre")
        view = self.client.get(items[0]["owner_url"])
        self.assertEqual(view.status_code, 200)
        self.assertContains(view, offer.name)
        self.assertContains(view, "14.50")
        self.assertContains(view, "Actuellement disponible")
        depth = self.selected("offer", offer.pk).json()["selection"]["owner_depth"]
        self.assertEqual(depth["facts"]["unit_price"], "14.50")
        self.assertTrue(depth["facts"]["currently_available"])
        self.assertEqual(depth["facts"]["currency"], "USD")
        self.assertTrue(depth["facts"]["can_manage_offer"])
        self.assertContains(view, "Modifier cette offre")
        self.assertNotIn(self.buyer.email, str(depth))

    def test_commerce_order_n2_historical_snapshots_not_current_offer_price(self):
        activity = self.activity()
        offer = self.offer(activity, amount="14.50")
        order = self.order(activity)
        self.order_line(order, offer, label="Kit acheté au prix ancien")
        offer.unit_price = Decimal("20.00")
        offer.save()
        selected = self.selected("commerce_order", order.pk)
        self.assertEqual(selected.status_code, 200)
        depth = selected.json()["selection"]["owner_depth"]
        self.assertEqual(depth["kind"], "commerce_order")
        self.assertEqual(depth["facts"]["total"], "18.00")
        self.assertEqual(depth["lines"]["items"][0]["unit_price"], "9.00")
        self.assertEqual(depth["lines"]["items"][0]["quantity"], 2)
        self.assertEqual(depth["lines"]["items"][0]["label"], "Kit acheté au prix ancien")
        self.assertEqual(depth["facts"]["payment_state"], "not_projected")
        self.assertEqual(depth["facts"]["delivery_state"], "not_projected")
        self.assertNotIn(self.buyer.email, str(selected.json()))
        web = self.client.get(self.depth("commerce_order", order.pk))
        self.assertEqual(web.status_code, 200)
        self.assertContains(web, "Kit acheté au prix ancien")
        self.assertContains(web, "Commande confirmée")
        self.assertNotContains(web, self.buyer.email)

    def test_commerce_order_many_lines_paginated_without_buyer_leak(self):
        activity = self.activity()
        offer = self.offer(activity)
        order = self.order(activity)
        for i in range(15):
            self.order_line(order, offer, label=f"Ligne réelle {i}")
        initial = self.selected("commerce_order", order.pk).json()["selection"]["owner_depth"]
        self.assertEqual(len(initial["lines"]["items"]), 12)
        self.assertTrue(initial["lines"]["has_more"])
        page = self.selected("commerce_order", order.pk, g3_offset=12)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(len(page.json()["selection"]["owner_depth"]["lines"]["items"]), 3)
        self.assertFalse(page.json()["selection"]["owner_depth"]["lines"]["has_more"])
        self.assertNotIn(self.buyer.email, str(page.json()))
        self.assertEqual(self.selected(
            "commerce_order", order.pk, g3_offset="-1",
        ).status_code, 400)
        self.assertEqual(self.client.get(
            self.work_url, {"g3_offset": "12"},
        ).status_code, 400)

    def test_activity_to_offer_relations_and_canonical_offer_creation(self):
        activity = self.activity()
        self.offer(activity, name="Offre préexistante")
        read = self.selected("activity", activity.pk)
        self.assertEqual(read.status_code, 200)
        owner = read.json()["selection"]["owner_depth"]
        self.assertEqual(owner["kind"], "commerce_activity")
        self.assertEqual(owner["offers"]["items"][0]["title"], "Offre préexistante")
        self.assertTrue(owner["facts"]["can_manage_offer"])
        web = self.client.get(self.depth("activity", activity.pk))
        self.assertEqual(web.status_code, 200)
        self.assertContains(web, "Créer une offre")
        create_url = reverse(
            "organizations_api:workspace-work-g3-offer-create",
            kwargs={"slug": self.space.slug, "activity_id": activity.pk},
        )
        form = {
            "name": "Nouvelle offre réelle", "description": "",
            "unit_price": "0.00", "currency": "USD",
            "payment_mode": "none", "min_quantity": "1",
            "max_quantity": "",
        }
        response = self.client.post(
            create_url, form, content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        result = response.json()
        created = Offer.objects.get(pk=result["offer"]["id"])
        self.assertEqual(created.activity_id, activity.pk)
        self.assertEqual(created.status, OfferStatus.DRAFT)
        self.assertEqual(result["responsibility"], "all")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertEqual(self.selected("offer", created.pk).status_code, 200)
        self.assertIn("Nouvelle offre réelle", str(self.selected(
            "activity", activity.pk,
        ).json()["selection"]["owner_depth"]))

    def test_offer_edit_is_owner_write_and_cannot_move_activity(self):
        activity = self.activity()
        offer = self.offer(activity, amount="14.50")
        url = reverse(
            "organizations_api:workspace-work-g3-offer-edit",
            kwargs={"slug": self.space.slug, "offer_id": offer.pk},
        )
        base = {
            "name": "Kit mis à jour", "description": "Détail",
            "unit_price": "7.50", "currency": "USD",
            "payment_mode": "upfront", "min_quantity": "1",
            "max_quantity": "3", "status": "active",
        }
        forged = self.client.post(
            url, {**base, "activity": str(activity.pk)},
            content_type="application/json",
        )
        self.assertEqual(forged.status_code, 400)
        valid = self.client.post(url, base, content_type="application/json")
        self.assertEqual(valid.status_code, 200, valid.content)
        offer.refresh_from_db()
        self.assertEqual(offer.name, "Kit mis à jour")
        self.assertEqual(offer.unit_price, Decimal("7.50"))
        self.assertEqual(offer.activity_id, activity.pk)
        web_url = reverse(
            "organizations:space-work-g3-offer-edit",
            kwargs={"slug": self.space.slug, "offer_id": offer.pk},
        )
        self.assertEqual(self.client.get(web_url).status_code, 200)
        invalid_mode = self.client.post(
            url, {**base, "payment_mode": "none"},
            content_type="application/json",
        )
        self.assertEqual(invalid_mode.status_code, 400)
        offer.refresh_from_db()
        self.assertEqual(offer.payment_mode, PaymentMode.UPFRONT)

    def test_offer_default_edit_preserves_other_allowed_modes(self):
        activity = self.activity()
        offer = self.offer(activity)
        set_offer_payment_modes(
            offer=offer,
            modes=[PaymentMode.UPFRONT, PaymentMode.ON_SITE],
        )
        url = reverse(
            "organizations_api:workspace-work-g3-offer-edit",
            kwargs={"slug": self.space.slug, "offer_id": offer.pk},
        )
        response = self.client.post(url, {
            "name": "Kit ajusté", "description": "",
            "unit_price": "15.50", "currency": "USD",
            "payment_mode": PaymentMode.UPFRONT, "min_quantity": "1",
            "max_quantity": "", "status": OfferStatus.ACTIVE,
        }, content_type="application/json")
        self.assertEqual(response.status_code, 200, response.content)
        offer.refresh_from_db()
        self.assertEqual(
            set(offer.allowed_payment_modes),
            {PaymentMode.UPFRONT, PaymentMode.ON_SITE},
        )

    def test_offer_other_space_and_revoked_mandate_never_transfer_authority(self):
        activity = self.activity()
        offer = self.offer(activity)
        foreign = Organization.objects.create(
            name="Autre Space", slug="mt5-foreign",
            created_by=self.owner,
        )
        foreign_activity = Activity.objects.create(
            title="Offre autre", space=foreign, created_by=self.owner,
            status=ActivityStatus.PUBLISHED,
        )
        foreign_offer = Offer.objects.create(
            activity=foreign_activity, name="Offre étrangère",
        )
        self.assertEqual(self.selected("offer", foreign_offer.pk).json()["selection"], None)
        self.assertEqual(self.client.get(
            self.depth("offer", foreign_offer.pk),
        ).status_code, 404)
        actor = User.objects.create_user(username="mt5-merchant", password="x")
        mandate = grant_activity_role(
            profile=actor, activity=activity,
            role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_login(actor)
        responsibility = f"mandate:{mandate.pk}"
        self.assertEqual(self.client.get(
            self.depth("offer", offer.pk, responsibility=responsibility),
        ).status_code, 200)
        self.assertEqual(self.client.get(
            self.depth("offer", foreign_offer.pk, responsibility=responsibility),
        ).status_code, 404)
        revoke_mandate(mandate=mandate, actor=self.owner)
        self.assertEqual(self.client.get(
            self.depth("offer", offer.pk, responsibility=responsibility),
        ).status_code, 404)

    def _transport(self):
        self.space.archetype = SpaceArchetype.TRANSPORT_OPERATOR
        self.space.save(update_fields=["archetype", "updated_at"])
        route = TransportRoute.objects.create(
            space=self.space, name="Route Lubumbashi → Kolwezi",
        )
        activity = self.activity("Service interurbain")
        # Activity management is not Operations authority. Exercise the
        # Departure operation under an explicit Activity Operations Mandate.
        grant_activity_role(
            profile=self.owner, activity=activity,
            role_code=SystemRoleCode.ACTIVITY_OPERATIONS_MANAGER,
            granted_by=self.owner,
        )
        TransportService.objects.create(activity=activity, route=route)
        vehicle = Vehicle.objects.create(
            space=self.space, label="Bus 18", passenger_capacity=40,
        )
        occurrence = Occurrence.objects.create(
            activity=activity, label="Départ du matin",
            start_at=timezone.now() + timedelta(days=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        pool = CapacityPool.objects.create(
            activity=activity, occurrence=occurrence,
            label="Voyageurs", total_quantity=24,
        )
        departure = TransportDeparture.objects.create(
            occurrence=occurrence, vehicle=vehicle,
            passenger_capacity_pool=pool,
        )
        return route, vehicle, activity, occurrence, departure

    def test_transport_n1_to_n2_route_vehicle_service_departure(self):
        route, vehicle, activity, occurrence, departure = self._transport()
        root = self.client.get(reverse(
            "organizations:space-work", kwargs={"slug": self.space.slug},
        ))
        self.assertEqual(root.status_code, 200)
        rows = [
            row for section in root.context["work_sections"]
            for row in section["items"]
        ]
        for kind, pk in (
            ("transport_route", route.pk),
            ("vehicle", vehicle.pk),
            ("activity", activity.pk),
            ("occurrence", occurrence.pk),
        ):
            match = next(row for row in rows if row["source"] == {
                "kind": kind, "id": str(pk),
            })
            self.assertIn("/work/g3/", match["owner_url"])
            detail = self.client.get(match["owner_url"])
            self.assertEqual(detail.status_code, 200)
        owner = self.selected("occurrence", occurrence.pk).json()["selection"]["owner_depth"]
        self.assertEqual(owner["kind"], "transport_departure")
        self.assertEqual(owner["facts"]["route"]["id"], str(route.pk))
        self.assertEqual(owner["facts"]["vehicle"]["id"], str(vehicle.pk))
        self.assertEqual(owner["facts"]["vehicle"]["physical_capacity"], 40)
        self.assertTrue(owner["facts"]["operations_visible"])
        self.assertNotIn("manifest", str(owner).lower())
        route_depth = self.selected("transport_route", route.pk).json()["selection"]["owner_depth"]
        self.assertEqual(route_depth["services"]["items"][0]["source"]["id"], str(activity.pk))
        self.assertEqual(route_depth["departures"]["items"][0]["source"]["id"], str(occurrence.pk))
        vehicle_depth = self.selected("vehicle", vehicle.pk).json()["selection"]["owner_depth"]
        self.assertEqual(vehicle_depth["departures"]["items"][0]["source"]["id"], str(occurrence.pk))
        service_depth = self.selected("activity", activity.pk).json()["selection"]["owner_depth"]
        self.assertEqual(service_depth["departures"]["items"][0]["source"]["id"], str(occurrence.pk))

    def test_transport_departure_without_vehicle_does_not_invent_one(self):
        route, vehicle, activity, occurrence, departure = self._transport()
        departure.vehicle = None
        departure.save(update_fields=["vehicle", "updated_at"])
        read = self.selected("occurrence", occurrence.pk).json()["selection"]["owner_depth"]
        self.assertTrue(read["facts"]["vehicle_assignment_known"])
        self.assertIsNone(read["facts"]["vehicle"])
        self.assertNotIn("readiness", str(read).lower())

    def test_transport_related_departures_bounded_and_elapsed_not_openable(self):
        route, vehicle, activity, occurrence, departure = self._transport()
        for n in range(15):
            date = timezone.now() + timedelta(days=n + 3)
            second = Occurrence.objects.create(
                activity=activity, label=f"Départ {n:02}",
                start_at=date, status=OccurrenceStatus.SCHEDULED,
            )
            pool = CapacityPool.objects.create(
                activity=activity, occurrence=second,
                total_quantity=20,
            )
            TransportDeparture.objects.create(
                occurrence=second, vehicle=vehicle,
                passenger_capacity_pool=pool,
            )
        first = self.selected("transport_route", route.pk)
        self.assertEqual(first.status_code, 200)
        page = first.json()["selection"]["owner_depth"]["departures"]
        self.assertEqual(len(page["items"]), 12)
        self.assertTrue(page["has_more"])
        continued = self.selected("transport_route", route.pk, g3_secondary_offset=12)
        self.assertEqual(continued.status_code, 200)
        self.assertEqual(len(continued.json()["selection"]["owner_depth"]["departures"]["items"]), 4)
        old = Occurrence.objects.create(
            activity=activity, label="Départ ancien non clôturé",
            start_at=timezone.now() - timedelta(days=4),
            end_at=timezone.now() - timedelta(days=3),
            status=OccurrenceStatus.SCHEDULED,
        )
        pool = CapacityPool.objects.create(
            activity=activity, occurrence=old, total_quantity=12,
        )
        TransportDeparture.objects.create(
            occurrence=old, vehicle=vehicle, passenger_capacity_pool=pool,
        )
        rows = self.selected("vehicle", vehicle.pk).json()["selection"]["owner_depth"]["departures"]["items"]
        old_row = next(row for row in rows if row["source"]["id"] == str(old.pk))
        self.assertFalse(old_row["openable"])

    def _places(self):
        a = Place.objects.create(
            name="Agence Lubumbashi", timezone="Africa/Lubumbashi",
            created_by=self.owner,
        )
        b = Place.objects.create(
            name="Agence Kolwezi", timezone="Africa/Lubumbashi",
            created_by=self.owner,
        )
        for place in (a, b):
            SpacePlace.objects.create(
                organization=self.space, place=place,
            )
        return a, b

    def test_transport_owner_creation_route_vehicle_departure_and_capacity(self):
        self.space.archetype = SpaceArchetype.TRANSPORT_OPERATOR
        self.space.save(update_fields=["archetype", "updated_at"])
        origin, destination = self._places()
        url = reverse(
            "organizations_api:workspace-work-g3-transport-create",
            kwargs={"slug": self.space.slug},
        )
        options = self.client.get(url)
        self.assertEqual(options.status_code, 200)
        self.assertTrue(options.json()["capabilities"]["create_route"])
        self.assertEqual(len(options.json()["places"]["items"]), 2)
        route_response = self.client.post(url, {
            "kind": "route", "origin": str(origin.pk),
            "destination": str(destination.pk),
        }, content_type="application/json")
        self.assertEqual(route_response.status_code, 201, route_response.content)
        route = TransportRoute.objects.get(
            pk=route_response.json()["created"]["id"],
        )
        self.assertEqual(route.space_id, self.space.pk)
        self.assertEqual(route.stops.count(), 2)
        vehicle_response = self.client.post(url, {
            "kind": "vehicle", "label": "Bus créé",
            "passenger_capacity": 30, "vehicle_type": "bus",
        }, content_type="application/json")
        self.assertEqual(vehicle_response.status_code, 201, vehicle_response.content)
        vehicle = Vehicle.objects.get(pk=vehicle_response.json()["created"]["id"])
        self.assertEqual(vehicle.passenger_capacity, 30)
        departure_response = self.client.post(url, {
            "kind": "departure", "route": str(route.pk),
            "vehicle": str(vehicle.pk),
            "start_at": (timezone.now() + timedelta(days=2)).isoformat(),
            "end_at": (timezone.now() + timedelta(days=2, hours=3)).isoformat(),
            "timezone": "Africa/Lubumbashi",
            "capacity": 20, "unit_price": "11.50",
            "currency": "USD", "payment_mode": "upfront",
            "fare_name": "Standard", "publish": True,
        }, content_type="application/json")
        self.assertEqual(departure_response.status_code, 201, departure_response.content)
        occurrence = Occurrence.objects.get(
            pk=departure_response.json()["created"]["id"],
        )
        self.assertEqual(occurrence.status, OccurrenceStatus.SCHEDULED)
        departure = occurrence.transport_departure
        self.assertEqual(departure.vehicle_id, vehicle.pk)
        self.assertEqual(departure.passenger_capacity_pool.total_quantity, 20)
        self.assertEqual(occurrence.offers.count(), 1)
        self.assertEqual(occurrence.offers.first().unit_price, Decimal("11.50"))
        self.assertEqual(occurrence.activity.status, ActivityStatus.PUBLISHED)
        self.assertEqual(departure_response["Cache-Control"], "private, no-store")

    def test_transport_invalid_departure_is_atomic_and_cross_space_denied(self):
        self.space.archetype = SpaceArchetype.TRANSPORT_OPERATOR
        self.space.save(update_fields=["archetype", "updated_at"])
        origin, dest = self._places()
        route = TransportRoute.objects.create(
            space=self.space, name="Route à vérifier",
        )
        from transport.models import TransportRouteStop
        TransportRouteStop.objects.create(
            route=route, place=origin, position=1,
        )
        TransportRouteStop.objects.create(
            route=route, place=dest, position=2,
        )
        vehicle = Vehicle.objects.create(
            space=self.space, label="Bus de 10 places", passenger_capacity=10,
        )
        url = reverse(
            "organizations_api:workspace-work-g3-transport-create",
            kwargs={"slug": self.space.slug},
        )
        request = {
            "kind": "departure", "route": str(route.pk),
            "vehicle": str(vehicle.pk),
            "start_at": (timezone.now() + timedelta(days=3)).isoformat(),
            "timezone": "Africa/Lubumbashi",
            "capacity": 25, "unit_price": "10.00",
            "currency": "USD", "payment_mode": "upfront",
        }
        invalid = self.client.post(url, request, content_type="application/json")
        self.assertEqual(invalid.status_code, 400, invalid.content)
        self.assertEqual(TransportDeparture.objects.count(), 0)
        self.assertEqual(TransportService.objects.count(), 0)
        self.assertFalse(Activity.objects.filter(
            title=route.name, space=self.space,
        ).exists())
        foreign = Organization.objects.create(
            name="Espace externe", slug="mt5-foreign-transport",
            created_by=self.owner,
        )
        foreign_route = TransportRoute.objects.create(
            space=foreign, name="Route privée",
        )
        other = self.client.post(
            url, {**request, "route": str(foreign_route.pk)},
            content_type="application/json",
        )
        self.assertEqual(other.status_code, 404)
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(
            url, {"kind": "vehicle", "label": "Infiltré",
                  "passenger_capacity": 12},
            content_type="application/json",
        ).status_code, 404)

    def test_transport_mandate_does_not_expose_whole_fleet_or_create(self):
        route, vehicle, activity, occurrence, departure = self._transport()
        actor = User.objects.create_user(
            username="mt5-transport-limited", password="x",
        )
        mandate = grant_activity_role(
            profile=actor, activity=activity,
            role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner,
        )
        self.client.force_login(actor)
        lens = f"mandate:{mandate.pk}"
        self.assertEqual(self.selected(
            "transport_route", route.pk, responsibility=lens,
        ).json()["selection"], None)
        self.assertEqual(self.client.get(
            self.depth("vehicle", vehicle.pk, responsibility=lens),
        ).status_code, 404)
        create_url = reverse(
            "organizations_api:workspace-work-g3-transport-create",
            kwargs={"slug": self.space.slug},
        )
        self.assertEqual(self.client.get(create_url).status_code, 404)
        self.assertEqual(self.client.post(
            create_url, {"kind": "vehicle", "label": "Interdit",
                         "passenger_capacity": 4},
            content_type="application/json",
        ).status_code, 404)
        revoke_mandate(mandate=mandate, actor=self.owner)
        self.assertEqual(self.client.get(
            self.depth("activity", activity.pk, responsibility=lens),
        ).status_code, 404)

    def test_owner_limits_and_invalid_types_fail_closed(self):
        self.space.archetype = SpaceArchetype.TRANSPORT_OPERATOR
        self.space.save(update_fields=["archetype", "updated_at"])
        url = reverse(
            "organizations_api:workspace-work-g3-transport-create",
            kwargs={"slug": self.space.slug},
        )
        for bad in (0, -1, "abc", True):
            response = self.client.post(url, {
                "kind": "vehicle", "label": "Impossible",
                "passenger_capacity": bad,
            }, content_type="application/json")
            self.assertEqual(response.status_code, 400, response.content)
        self.assertEqual(Vehicle.objects.filter(label="Impossible").count(), 0)
        self.assertEqual(self.client.get(
            url, {"routes_offset": "-1"},
        ).status_code, 400)
        self.assertEqual(self.client.post(url, {
            "kind": "route", "origin": "foreign", "destination": "unknown",
        }, content_type="application/json").status_code, 400)
