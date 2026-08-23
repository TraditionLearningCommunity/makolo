from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from access.models import Access, AccessStatus
from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from capacity.models import CapacityPool, CapacityReservation, CapacityReservationStatus
from commerce.models import CommerceOrder, Offer, OfferStatus, PaymentMode
from events.models import Event
from journeys.models import Journey, JourneyRequest, JourneyStatus, RequestPurpose, WorkflowKind

from .search import search_occurrences


User = get_user_model()


class DiscoveryParticipantStateTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="discovery-state-owner",
            email="discovery-state-owner@task17.test",
            password="test-pass",
        )
        self.profile = User.objects.create_user(
            username="discovery-state-profile",
            email="discovery-state-profile@task17.test",
            password="test-pass",
        )
        self.other = User.objects.create_user(
            username="discovery-state-other",
            email="discovery-state-other@task17.test",
            password="test-pass",
        )
        self.now = timezone.now()
        self.activity = Activity.objects.create(
            title="Forum canonique participant",
            short_description="Une activité de test participant.",
            created_by=self.owner,
            status=ActivityStatus.PUBLISHED,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=self.now + timedelta(days=2),
            end_at=self.now + timedelta(days=2, hours=2),
            timezone="Africa/Lubumbashi",
            status=OccurrenceStatus.SCHEDULED,
        )
        self.event = Event.objects.create(activity=self.activity, published_at=self.now)
        self.pool = CapacityPool.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            label="Billets",
            total_quantity=20,
        )
        self.offer = Offer.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            capacity_pool=self.pool,
            name="Standard",
            unit_price=Decimal("10.00"),
            currency="USD",
            payment_mode=PaymentMode.UPFRONT,
            status=OfferStatus.ACTIVE,
        )

    def journey(self, *, status=JourneyStatus.DRAFT, workflow=WorkflowKind.PURCHASE, profile=None):
        profile = profile or self.profile
        return Journey.objects.create(
            initiated_by=profile,
            beneficiary=profile,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=workflow,
            status=status,
        )

    def discovery_item(self, profile=None):
        result = search_occurrences(
            {"q": "Forum canonique participant"},
            profile=profile,
            now=self.now,
        )
        self.assertEqual(result.total, 1)
        return result.items[0]

    def test_anonymous_and_connected_without_relation_keep_public_action(self):
        anonymous = self.discovery_item()
        self.assertEqual(anonymous.participant.participant_state, "none")
        self.assertEqual(anonymous.cta_label, "Acheter le billet")
        connected = self.discovery_item(self.profile)
        self.assertEqual(connected.participant.participant_state, "none")
        self.assertEqual(connected.cta_label, "Acheter le billet")

    def test_valid_access_changes_discovery_and_event_detail_with_same_state(self):
        access = Access.objects.create(
            beneficiary=self.profile,
            activity=self.activity,
            occurrence=self.occurrence,
            status=AccessStatus.VALID,
        )
        item = self.discovery_item(self.profile)
        self.assertEqual(item.participant.participant_state, "access_valid")
        self.assertEqual(item.participant.label, "Vous avez accès")
        self.assertEqual(item.cta_url, reverse("core:participant-access-detail", kwargs={"pk": access.pk}))
        self.assertNotEqual(item.cta_label, "Acheter le billet")

        self.client.force_login(self.profile)
        response = self.client.get(reverse("events:detail", kwargs={"slug": self.event.slug}))
        self.assertEqual(response.status_code, 200)
        event_state = response.context["participant_presentation"]
        self.assertEqual(event_state.participant_state, item.participant.participant_state)
        self.assertEqual(event_state.label, item.participant.label)
        self.assertEqual(event_state.primary_url, item.cta_url)
        self.assertContains(response, "Vous avez accès")
        self.assertNotContains(response, ">Obtenir des billets<")

    def test_used_and_revoked_access_remain_visible(self):
        for status, expected in (
            (AccessStatus.USED, "Accès utilisé"),
            (AccessStatus.REVOKED, "Accès révoqué"),
        ):
            with self.subTest(status=status):
                Access.objects.all().delete()
                Access.objects.create(
                    beneficiary=self.profile,
                    activity=self.activity,
                    occurrence=self.occurrence,
                    status=status,
                )
                item = self.discovery_item(self.profile)
                self.assertEqual(item.participant.label, expected)
                self.assertNotEqual(item.cta_label, "Acheter le billet")

    def test_pending_request_and_hold_have_contextual_discovery_actions(self):
        journey = self.journey(status=JourneyStatus.PENDING_APPROVAL, workflow=WorkflowKind.ORDER_APPROVAL)
        JourneyRequest.objects.create(
            journey=journey,
            requester=self.profile,
            purpose=RequestPurpose.APPROVAL,
            expires_at=self.now + timedelta(hours=2),
        )
        item = self.discovery_item(self.profile)
        self.assertEqual(item.participant.label, "Demande envoyée")
        self.assertEqual(item.cta_url, reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}))

        JourneyRequest.objects.all().delete()
        CapacityReservation.objects.create(
            pool=self.pool,
            journey=journey,
            quantity=1,
            status=CapacityReservationStatus.HELD,
            expires_at=self.now + timedelta(minutes=30),
        )
        item = self.discovery_item(self.profile)
        self.assertEqual(item.participant.label, "Place retenue temporairement")
        self.assertTrue(item.participant.secondary_label.startswith("Jusqu’à "))

    def test_pending_payment_points_to_existing_commerce_resource_and_enforces_owner(self):
        journey = self.journey(status=JourneyStatus.PENDING_PAYMENT)
        order = CommerceOrder.objects.create(
            journey=journey,
            buyer=self.profile,
            payment_mode=PaymentMode.UPFRONT,
            subtotal=Decimal("10.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("10.00"),
            expires_at=self.now + timedelta(hours=1),
        )
        item = self.discovery_item(self.profile)
        expected = reverse("payments:commerce-start", kwargs={"order_pk": order.pk})
        self.assertEqual(item.participant.label, "Paiement en attente")
        self.assertEqual(item.cta_label, "Reprendre le paiement")
        self.assertEqual(item.cta_url, expected)

        self.client.force_login(self.profile)
        self.assertEqual(self.client.get(expected).status_code, 200)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(expected).status_code, 404)

    def test_sold_out_without_relation_has_no_purchase_cta(self):
        journey = self.journey(status=JourneyStatus.EXPIRED)
        CapacityReservation.objects.create(
            pool=self.pool,
            journey=journey,
            quantity=20,
            status=CapacityReservationStatus.COMMITTED,
        )
        item = self.discovery_item(self.profile)
        self.assertEqual(item.participant.availability, "sold_out")
        self.assertEqual(item.participant.availability_label, "Complet")
        self.assertNotEqual(item.cta_label, "Acheter le billet")

    def test_cancelled_event_keeps_participant_history_reachable_without_purchase(self):
        access = Access.objects.create(
            beneficiary=self.profile,
            activity=self.activity,
            occurrence=self.occurrence,
            status=AccessStatus.USED,
        )
        Activity.objects.filter(pk=self.activity.pk).update(status=ActivityStatus.CANCELLED)
        Occurrence.objects.filter(pk=self.occurrence.pk).update(status=OccurrenceStatus.CANCELLED)
        self.activity.refresh_from_db()
        self.occurrence.refresh_from_db()

        self.client.force_login(self.profile)
        response = self.client.get(reverse("events:detail", kwargs={"slug": self.event.slug}))
        self.assertEqual(response.status_code, 200)
        state = response.context["participant_presentation"]
        self.assertEqual(state.availability, "cancelled")
        self.assertEqual(state.label, "Accès utilisé")
        self.assertEqual(state.primary_url, reverse("core:participant-access-detail", kwargs={"pk": access.pk}))
        self.assertNotContains(response, "Acheter le billet")

    def test_professional_and_participant_states_coexist(self):
        professional_activity = Activity.objects.create(
            title="Événement double identité",
            created_by=self.profile,
            status=ActivityStatus.PUBLISHED,
        )
        occurrence = Occurrence.objects.create(
            activity=professional_activity,
            start_at=self.now + timedelta(days=3),
            end_at=self.now + timedelta(days=3, hours=2),
            status=OccurrenceStatus.SCHEDULED,
        )
        event = Event.objects.create(activity=professional_activity, published_at=self.now)
        access = Access.objects.create(
            beneficiary=self.profile,
            activity=professional_activity,
            occurrence=occurrence,
            status=AccessStatus.VALID,
        )
        self.client.force_login(self.profile)
        response = self.client.get(reverse("events:detail", kwargs={"slug": event.slug}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["can_manage_event"])
        self.assertEqual(response.context["participant_presentation"].participant_state, "access_valid")
        self.assertContains(response, "Gérer")
        self.assertContains(response, reverse("core:participant-access-detail", kwargs={"pk": access.pk}))

    def test_other_participant_access_does_not_change_professional_personal_state(self):
        Access.objects.create(
            beneficiary=self.other,
            activity=self.activity,
            occurrence=self.occurrence,
            status=AccessStatus.VALID,
        )
        item = self.discovery_item(self.owner)
        self.assertEqual(item.participant.participant_state, "none")
        self.assertEqual(item.cta_label, "Acheter le billet")

    def test_discovery_participant_loading_has_no_per_card_query_growth(self):
        for index in range(5):
            activity = Activity.objects.create(
                title=f"Forum secondaire {index}",
                created_by=self.owner,
                status=ActivityStatus.PUBLISHED,
            )
            occurrence = Occurrence.objects.create(
                activity=activity,
                start_at=self.now + timedelta(days=4 + index),
                end_at=self.now + timedelta(days=4 + index, hours=1),
                status=OccurrenceStatus.SCHEDULED,
            )
            Event.objects.create(activity=activity, published_at=self.now)
            pool = CapacityPool.objects.create(
                activity=activity,
                occurrence=occurrence,
                label="Places",
                total_quantity=10,
            )
            Offer.objects.create(
                activity=activity,
                occurrence=occurrence,
                capacity_pool=pool,
                name="Standard",
                unit_price=Decimal("5.00"),
                payment_mode=PaymentMode.UPFRONT,
                status=OfferStatus.ACTIVE,
            )
        with CaptureQueriesContext(connection) as queries:
            result = search_occurrences({}, profile=self.profile, now=self.now)
            list(result.items)
        self.assertEqual(result.total, 6)
        self.assertLessEqual(len(queries), 16)
