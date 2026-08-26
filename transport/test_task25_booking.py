from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from access.models import Access
from commerce.models import CommerceOrder, PaymentMode
from geography.models import Place
from journeys.beneficiary_services import create_external_beneficiary
from journeys.models import Journey
from organizations.models import Organization

from .models import Vehicle
from .services import (
    book_transport,
    configure_transport_fare,
    create_transport_departure,
    create_transport_route,
    create_transport_service,
    publish_transport_departure,
)


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
class Task25TransportBookingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.buyer = User.objects.create_user(username="sarah-t25", email="sarah-t25@example.test", password="pass-12345")
        self.other_profile = User.objects.create_user(username="jacques-t25", email="jacques-t25@example.test", password="pass-12345")
        self.stranger = User.objects.create_user(username="stranger-t25", email="stranger-t25@example.test", password="pass-12345")
        self.space = Organization.objects.create(name="T25 Transport", slug="t25-transport", created_by=self.buyer)
        self.origin = Place.objects.create(name="Kolwezi Gare", locality="Kolwezi", country_code="CD", timezone="Africa/Lubumbashi")
        self.destination = Place.objects.create(name="Lubumbashi Gare", locality="Lubumbashi", country_code="CD", timezone="Africa/Lubumbashi")
        self.route = create_transport_route(space=self.space, name="Kolwezi Lubumbashi T25", stops=[self.origin, self.destination])
        self.service = create_transport_service(space=self.space, created_by=self.buyer, route=self.route)
        self.vehicle = Vehicle.objects.create(space=self.space, label="T25 Bus", passenger_capacity=10)
        self.departure = create_transport_departure(
            service=self.service,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=4),
            timezone_name="Africa/Lubumbashi",
            vehicle=self.vehicle,
            capacity=10,
        )
        self.offer = configure_transport_fare(
            departure=self.departure,
            name="Flexible T25",
            unit_price=Decimal("20.00"),
            payment_mode=PaymentMode.UPFRONT,
            payment_modes=[PaymentMode.UPFRONT, PaymentMode.ON_SITE],
        )
        publish_transport_departure(departure=self.departure)

    def test_same_retry_reuses_journey_order_and_access(self):
        first = book_transport(
            departure=self.departure,
            offer=self.offer,
            participant=self.buyer,
            payment_mode=PaymentMode.ON_SITE,
            idempotency_key="t25-retry-one",
        )
        second = book_transport(
            departure=self.departure,
            offer=self.offer,
            participant=self.buyer,
            payment_mode=PaymentMode.ON_SITE,
            idempotency_key="t25-retry-one",
        )
        self.assertEqual(first["order"].pk, second["order"].pk)
        self.assertEqual(first["journey"].pk, second["journey"].pk)
        self.assertEqual(first["access"].pk, second["access"].pk)
        self.assertEqual(CommerceOrder.objects.filter(buyer=self.buyer).count(), 1)
        self.assertEqual(Journey.objects.filter(initiated_by=self.buyer).count(), 1)
        self.assertEqual(Access.objects.filter(journey=first["journey"]).count(), 1)

    def test_explicit_new_purchase_creates_new_individual_access(self):
        first = book_transport(
            departure=self.departure,
            offer=self.offer,
            participant=self.buyer,
            payment_mode=PaymentMode.ON_SITE,
            idempotency_key="t25-buy-one",
        )
        second = book_transport(
            departure=self.departure,
            offer=self.offer,
            participant=self.buyer,
            payment_mode=PaymentMode.ON_SITE,
            idempotency_key="t25-buy-two",
        )
        self.assertNotEqual(first["order"].pk, second["order"].pk)
        self.assertNotEqual(first["access"].pk, second["access"].pk)
        self.assertEqual(CommerceOrder.objects.filter(buyer=self.buyer).count(), 2)
        self.assertEqual(Access.objects.filter(beneficiary=self.buyer, occurrence=self.departure.occurrence).count(), 2)

    def test_buyer_can_book_for_existing_profile(self):
        result = book_transport(
            departure=self.departure,
            offer=self.offer,
            participant=self.buyer,
            beneficiary=self.other_profile,
            payment_mode=PaymentMode.ON_SITE,
            idempotency_key="t25-profile-holder",
        )
        self.assertEqual(result["journey"].initiated_by_id, self.buyer.pk)
        self.assertEqual(result["journey"].beneficiary_id, self.other_profile.pk)
        self.assertEqual(result["access"].beneficiary_id, self.other_profile.pk)
        self.assertIsNone(result["access"].external_beneficiary_id)

    def test_buyer_can_book_for_guest_without_creating_user(self):
        before_users = get_user_model().objects.count()
        guest = create_external_beneficiary(
            created_by=self.buyer,
            display_name="Jacques Invité",
            email="jacques.guest@example.test",
            phone="+243990000001",
        )
        result = book_transport(
            departure=self.departure,
            offer=self.offer,
            participant=self.buyer,
            beneficiary=None,
            external_beneficiary=guest,
            payment_mode=PaymentMode.ON_SITE,
            idempotency_key="t25-guest-holder",
        )
        self.assertEqual(get_user_model().objects.count(), before_users)
        self.assertIsNone(result["journey"].beneficiary_id)
        self.assertEqual(result["journey"].external_beneficiary_id, guest.pk)
        self.assertIsNone(result["access"].beneficiary_id)
        self.assertEqual(result["access"].external_beneficiary_id, guest.pk)
        self.assertEqual(result["access"].beneficiary_display_name, "Jacques Invité")
        self.assertEqual(result["access"].credentials.count(), 1)
        self.assertFalse(result["order"].payments.exists())

    def test_offer_payment_choice_is_snapshotted_and_forged_choice_rejected(self):
        on_site = book_transport(
            departure=self.departure,
            offer=self.offer,
            participant=self.buyer,
            payment_mode=PaymentMode.ON_SITE,
            idempotency_key="t25-onsite-choice",
        )
        self.assertEqual(on_site["order"].payment_mode, PaymentMode.ON_SITE)
        self.assertEqual(on_site["order"].status, "confirmed")
        self.assertFalse(on_site["order"].payments.exists())
        with self.assertRaises(ValidationError):
            book_transport(
                departure=self.departure,
                offer=self.offer,
                participant=self.other_profile,
                payment_mode=PaymentMode.LATER,
                idempotency_key="t25-forged-choice",
            )

    def test_buyer_can_open_guest_ticket_but_stranger_cannot(self):
        guest = create_external_beneficiary(created_by=self.buyer, display_name="Guest T25")
        result = book_transport(
            departure=self.departure,
            offer=self.offer,
            participant=self.buyer,
            external_beneficiary=guest,
            payment_mode=PaymentMode.ON_SITE,
            idempotency_key="t25-guest-visible",
        )
        self.client.force_login(self.buyer)
        response = self.client.get(reverse("core:participant-access-detail", kwargs={"pk": result["access"].pk}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Billet acheté pour Guest T25")
        self.client.force_login(self.stranger)
        denied = self.client.get(reverse("core:participant-access-detail", kwargs={"pk": result["access"].pk}))
        self.assertEqual(denied.status_code, 404)

    def test_departure_page_makes_repeat_purchase_explicit(self):
        book_transport(
            departure=self.departure,
            offer=self.offer,
            participant=self.buyer,
            payment_mode=PaymentMode.ON_SITE,
            idempotency_key="t25-existing-ticket-ui",
        )
        self.client.force_login(self.buyer)
        response = self.client.get(reverse("transport:departure-detail", kwargs={"pk": self.departure.pk}))
        self.assertContains(response, "Vous avez déjà acheté 1 billet")
        self.assertContains(response, "Acheter un autre billet")

    def test_same_origin_destination_is_server_validated_without_500(self):
        response = self.client.get(
            reverse("transport:search"),
            {"origin": str(self.origin.pk), "destination": str(self.origin.pk), "date": (timezone.localdate() + timedelta(days=2)).isoformat()},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Le départ et la destination doivent être différents.")
        self.assertContains(response, "data-transport-search-form")
