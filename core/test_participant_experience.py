from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from access.models import Access, AccessCredential, AccessStatus
from activities.models import Activity, ActivityStatus, Occurrence, OccurrencePlace, OccurrenceStatus
from commerce.models import CommerceOrder, CommerceOrderStatus, PaymentMode
from geography.models import Place
from journeys.models import Journey, JourneyStatus, WorkflowKind
from notifications.models import Notification
from payments.models import Payment

from .participant_presentation import (
    access_status_label,
    journey_status_label,
    next_participant_action,
    occurrence_timing,
    payment_mode_label,
    vocabulary_for,
)
from .participant_selectors import participant_accesses, participant_journeys, participant_orders


User = get_user_model()


class ParticipantExperienceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="participant-test",
            email="participant@example.test",
            password="secret-test-password",
        )
        self.other = User.objects.create_user(
            username="other-test",
            email="other@example.test",
            password="secret-test-password",
        )
        self.activity = Activity.objects.create(
            title="Atelier communautaire",
            created_by=self.user,
            status=ActivityStatus.PUBLISHED,
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=1, hours=2),
            timezone="Africa/Kinshasa",
            status=OccurrenceStatus.SCHEDULED,
        )
        self.place = Place.objects.create(name="Maison des initiatives", locality="Kinshasa")
        OccurrencePlace.objects.create(occurrence=self.occurrence, place=self.place, role="primary")
        self.journey = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.CONFIRMED,
        )
        self.access = Access.objects.create(
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            journey=self.journey,
            status=AccessStatus.VALID,
        )
        AccessCredential.objects.create(access=self.access)

    def test_non_event_activity_is_visible_without_ticket_models_or_payment(self):
        self.assertFalse(hasattr(self.activity, "event_vertical"))
        self.assertEqual(list(participant_journeys(self.user)), [self.journey])
        self.assertEqual(list(participant_accesses(self.user)), [self.access])
        self.assertEqual(Payment.objects.count(), 0)

    def test_centralized_labels_and_next_action(self):
        self.assertEqual(journey_status_label(JourneyStatus.PENDING_APPROVAL), "En attente de validation")
        self.assertEqual(access_status_label(AccessStatus.TRANSFERRED), "Transféré")
        self.journey.status = JourneyStatus.PENDING_PAYMENT
        self.assertEqual(next_participant_action(self.journey), "Payer")

    def test_occurrence_timing_uses_occurrence_timezone(self):
        self.occurrence.start_at = datetime(2030, 1, 15, 17, 0, tzinfo=dt_timezone.utc)
        self.occurrence.timezone = "Africa/Kinshasa"
        timing = occurrence_timing(self.occurrence)
        self.assertEqual(timing.time_label, "18:00")
        self.assertEqual(timing.timezone_label, "Africa/Kinshasa")

    def test_payment_and_workflow_vocabulary_are_contextual(self):
        self.assertEqual(payment_mode_label(PaymentMode.NONE), "")
        self.assertEqual(payment_mode_label(PaymentMode.ON_SITE), "À payer sur place")
        self.assertEqual(
            vocabulary_for(activity=self.activity, workflow=WorkflowKind.REGISTRATION).access_noun,
            "Confirmation",
        )
        self.assertEqual(
            vocabulary_for(activity=self.activity, workflow=WorkflowKind.RESERVATION).access_noun,
            "Réservation",
        )
        self.assertEqual(
            vocabulary_for(activity=self.activity, workflow=WorkflowKind.INVITATION).access_noun,
            "Invitation",
        )

    def test_pending_payment_uses_commerce_order_and_real_payment_endpoint(self):
        journey = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.PURCHASE,
            status=JourneyStatus.PENDING_PAYMENT,
        )
        order = CommerceOrder.objects.create(
            journey=journey,
            buyer=self.user,
            payment_mode=PaymentMode.UPFRONT,
            currency="USD",
            subtotal=Decimal("12.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("12.00"),
        )

        self.assertEqual(list(participant_orders(self.user)), [order])
        self.assertFalse(participant_orders(self.other).exists())

        self.client.force_login(self.user)
        response = self.client.get(
            reverse("core:participant-journey-detail", kwargs={"pk": journey.pk})
        )
        payment_url = reverse("payments:commerce-start", kwargs={"order_pk": order.pk})
        self.assertContains(response, "Paiement en ligne requis")
        self.assertContains(response, "12,00 USD")
        self.assertContains(response, payment_url)
        self.assertEqual(self.client.get(payment_url).status_code, 200)

    def test_on_site_reservation_is_not_presented_as_unpaid_or_online_payment(self):
        journey = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.RESERVATION,
            status=JourneyStatus.CONFIRMED,
        )
        order = CommerceOrder.objects.create(
            journey=journey,
            buyer=self.user,
            status=CommerceOrderStatus.CONFIRMED,
            payment_mode=PaymentMode.ON_SITE,
            currency="USD",
            subtotal=Decimal("20.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("20.00"),
        )

        self.client.force_login(self.user)
        response = self.client.get(reverse("core:participant-journey-detail", kwargs={"pk": journey.pk}))
        self.assertContains(response, "À payer sur place")
        self.assertNotContains(response, reverse("payments:commerce-start", kwargs={"order_pk": order.pk}))
        self.assertEqual(Payment.objects.count(), 0)

    def test_invitation_beneficiary_can_accept_once_and_receives_access(self):
        invitation = Journey.objects.create(
            initiated_by=self.other,
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.INVITATION,
            status=JourneyStatus.SUBMITTED,
        )
        self.client.force_login(self.user)
        detail = self.client.get(reverse("core:participant-journey-detail", kwargs={"pk": invitation.pk}))
        self.assertContains(detail, "Répondre à l’invitation")
        self.assertContains(detail, "Accepter l’invitation")

        response = self.client.post(reverse("core:participant-invitation-accept", kwargs={"pk": invitation.pk}))
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, JourneyStatus.CONFIRMED)
        access = Access.objects.get(journey=invitation, source_key="participant-invitation")
        self.assertRedirects(response, reverse("core:participant-access-detail", kwargs={"pk": access.pk}))
        self.assertTrue(access.credentials.filter(status="active").exists())

        retry = self.client.post(reverse("core:participant-invitation-accept", kwargs={"pk": invitation.pk}))
        self.assertRedirects(retry, reverse("core:participant-access-detail", kwargs={"pk": access.pk}))
        self.assertEqual(Access.objects.filter(journey=invitation, source_key="participant-invitation").count(), 1)

        self.client.force_login(self.other)
        forbidden = self.client.post(reverse("core:participant-invitation-accept", kwargs={"pk": invitation.pk}))
        self.assertEqual(forbidden.status_code, 404)

    def test_invitation_beneficiary_can_decline_without_access(self):
        invitation = Journey.objects.create(
            initiated_by=self.other,
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.INVITATION,
            status=JourneyStatus.SUBMITTED,
        )
        self.client.force_login(self.user)
        response = self.client.post(reverse("core:participant-invitation-decline", kwargs={"pk": invitation.pk}))
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, JourneyStatus.CANCELLED)
        self.assertRedirects(response, reverse("core:participant-journey-detail", kwargs={"pk": invitation.pk}))
        self.assertFalse(Access.objects.filter(journey=invitation).exists())

    def test_participant_pages_show_canonical_occurrence_place_and_access(self):
        self.client.force_login(self.user)
        home = self.client.get(reverse("core:participant-home"))
        self.assertContains(home, "Atelier communautaire")
        self.assertContains(home, "Kinshasa")
        detail = self.client.get(reverse("core:participant-journey-detail", kwargs={"pk": self.journey.pk}))
        self.assertContains(detail, "Inscription")
        self.assertContains(detail, "Maison des initiatives")
        self.assertContains(detail, "Africa/Kinshasa")
        access = self.client.get(reverse("core:participant-access-detail", kwargs={"pk": self.access.pk}))
        self.assertContains(access, "Confirmation")
        self.assertContains(access, "data:image/png;base64")
        self.assertContains(access, "Africa/Kinshasa")

    def test_notifications_open_canonical_journey_and_access_details(self):
        self.client.force_login(self.user)
        journey_notification = Notification.objects.create(
            recipient=self.user,
            activity=self.activity,
            journey=self.journey,
            title="Paiement requis",
            message="Action requise.",
            action_url="/tickets/legacy-order/",
        )
        access_notification = Notification.objects.create(
            recipient=self.user,
            activity=self.activity,
            journey=self.journey,
            access=self.access,
            title="Accès disponible",
            message="Votre accès est disponible.",
            action_url="/tickets/legacy-ticket/",
        )

        journey_response = self.client.get(
            reverse("notifications:open", kwargs={"pk": journey_notification.pk})
        )
        access_response = self.client.get(
            reverse("notifications:open", kwargs={"pk": access_notification.pk})
        )

        self.assertRedirects(
            journey_response,
            reverse("core:participant-journey-detail", kwargs={"pk": self.journey.pk}),
        )
        self.assertRedirects(
            access_response,
            reverse("core:participant-access-detail", kwargs={"pk": self.access.pk}),
        )

    def test_ownership_hides_other_participant_objects(self):
        self.client.force_login(self.other)
        journey_response = self.client.get(reverse("core:participant-journey-detail", kwargs={"pk": self.journey.pk}))
        access_response = self.client.get(reverse("core:participant-access-detail", kwargs={"pk": self.access.pk}))
        self.assertEqual(journey_response.status_code, 404)
        self.assertEqual(access_response.status_code, 404)
