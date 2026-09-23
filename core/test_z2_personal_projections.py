from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity, Occurrence, OccurrenceTimingKind
from events.models import Event, EventStatus, EventVisibility
from journeys.collaboration_models import JourneyStep
from journeys.models import Journey, JourneyStatus, WorkflowKind
from tickets.models import TicketWaitlistEntry, WaitlistStatus
from tickets.services import create_order

from core.api.personal_projections import (
    build_personal_now_projection,
    build_personal_ongoing_projection,
)


User = get_user_model()


class Z2ProjectionAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="z2-user",
            email="z2-user@example.test",
            password="Strong-Z2-Password-2026!",
        )
        self.other = User.objects.create_user(
            username="z2-other",
            email="z2-other@example.test",
            password="Strong-Z2-Password-2026!",
        )

    def test_personal_projection_endpoints_require_authentication(self):
        for url in (
            reverse("personal-projections:now"),
            reverse("personal-projections:ongoing"),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertIn(response.status_code, {401, 403})

    def test_empty_personal_projections_use_stable_empty_items(self):
        self.client.force_login(self.user)
        now_response = self.client.get(reverse("personal-projections:now"))
        ongoing_response = self.client.get(reverse("personal-projections:ongoing"))

        self.assertEqual(now_response.status_code, 200)
        self.assertEqual(ongoing_response.status_code, 200)
        self.assertEqual(now_response.json()["meta"]["projection"], "personal.now")
        self.assertEqual(ongoing_response.json()["meta"]["projection"], "personal.ongoing")
        self.assertEqual(now_response.json()["data"], {"items": []})
        self.assertEqual(ongoing_response.json()["data"], {"items": []})
        self.assertNotIn("all_clear", now_response.json()["data"])
        self.assertEqual(now_response["Cache-Control"], "private, no-store")
        self.assertEqual(ongoing_response["Cache-Control"], "private, no-store")

    def test_personal_projection_endpoints_reject_client_selected_actor(self):
        self.client.force_login(self.user)
        attempts = (
            ("user_id", self.other.pk),
            ("beneficiary_id", self.other.pk),
            ("subject_id", self.other.pk),
            ("space_id", "00000000-0000-0000-0000-000000000001"),
            ("act_as_space", "1"),
        )
        for url in (
            reverse("personal-projections:now"),
            reverse("personal-projections:ongoing"),
        ):
            for key, value in attempts:
                with self.subTest(url=url, key=key):
                    response = self.client.get(url, {key: value})
                    self.assertEqual(response.status_code, 400)
                    self.assertIn(key, response.json())


class Z2JourneyBoundaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="z2-journey",
            email="z2-journey@example.test",
            password="Strong-Z2-Password-2026!",
        )
        self.other = User.objects.create_user(
            username="z2-journey-other",
            email="z2-journey-other@example.test",
            password="Strong-Z2-Password-2026!",
        )
        self.activity = Activity.objects.create(
            created_by=self.user,
            owner_profile=self.user,
            title="Démarche Z2",
        )
        self.journey = Journey.objects.create(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.APPROVED,
        )

    def test_future_actor_step_stays_ongoing_without_entering_now_until_due(self):
        step = JourneyStep.objects.create(
            journey=self.journey,
            title="Fournir l’attestation",
            position=10,
            is_required=True,
            due_at=timezone.now() + timedelta(days=7),
            created_by=self.user,
        )

        ongoing = build_personal_ongoing_projection(self.user)
        now = build_personal_now_projection(self.user)

        journey_item = next(
            item for item in ongoing["items"]
            if item["source"] == {"kind": "journey", "id": str(self.journey.pk)}
        )
        self.assertEqual(len(journey_item["actor_interventions"]), 1)
        self.assertFalse(
            any(
                item["source"] == {"kind": "journey", "id": str(self.journey.pk)}
                for item in now["items"]
            )
        )

        step.due_at = timezone.now() + timedelta(hours=1)
        step.save(update_fields=["due_at", "updated_at"])

        current = build_personal_now_projection(self.user)
        self.assertTrue(
            any(
                item["source"] == {"kind": "journey", "id": str(self.journey.pk)}
                and item["dimension"] == "action"
                for item in current["items"]
            )
        )

    def test_foreign_journey_never_leaks_into_personal_projection(self):
        foreign_activity = Activity.objects.create(
            created_by=self.other,
            owner_profile=self.other,
            title="Démarche privée étrangère",
        )
        foreign = Journey.objects.create(
            initiated_by=self.other,
            beneficiary=self.other,
            activity=foreign_activity,
            workflow=WorkflowKind.REGISTRATION,
            status=JourneyStatus.DRAFT,
        )

        now = build_personal_now_projection(self.user)
        ongoing = build_personal_ongoing_projection(self.user)
        sources = {
            (item["source"]["kind"], item["source"]["id"])
            for item in now["items"] + ongoing["items"]
        }
        self.assertNotIn(("journey", str(foreign.pk)), sources)

    def test_date_only_occurrence_keeps_date_without_invented_midnight(self):
        occurrence = Occurrence.objects.create(
            activity=self.activity,
            timing_kind=OccurrenceTimingKind.DATE_ONLY,
            start_date=(timezone.localdate() + timedelta(days=2)),
        )
        self.journey.occurrence = occurrence
        self.journey.save(update_fields=["occurrence", "updated_at"])

        ongoing = build_personal_ongoing_projection(self.user)
        journey_item = next(
            item for item in ongoing["items"]
            if item["source"] == {"kind": "journey", "id": str(self.journey.pk)}
        )
        self.assertEqual(
            journey_item["timing"]["start_date"],
            occurrence.start_date.isoformat(),
        )
        self.assertNotIn("start_at", journey_item["timing"])


class Z2WaitlistBoundaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="z2-waiter",
            email="z2-waiter@example.test",
            password="Strong-Z2-Password-2026!",
        )
        self.owner = User.objects.create_user(
            username="z2-owner",
            email="z2-owner@example.test",
            password="Strong-Z2-Password-2026!",
        )
        start = timezone.now() + timedelta(days=7)
        self.event = Event.objects.create(
            organizer=self.owner,
            title="Z2 occurrence",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=2),
            registration_start_at=timezone.now() - timedelta(hours=1),
            registration_end_at=start,
            capacity=2,
            published_at=timezone.now(),
        )
        self.ticket_type = self.event.ticket_types.create(
            name="Z2 place",
            price="0.00",
            quantity_total=2,
            max_per_order=1,
        )
        self.owner_order = create_order(
            buyer=self.owner,
            event=self.event,
            customer_name="Owner",
            customer_email=self.owner.email,
            selections=[(self.ticket_type, 1)],
        )

    def test_waiting_is_ongoing_not_now_and_offer_is_both(self):
        entry = TicketWaitlistEntry.objects.create(
            ticket_type=self.ticket_type,
            user=self.user,
            status=WaitlistStatus.WAITING,
        )

        ongoing = build_personal_ongoing_projection(self.user)
        now = build_personal_now_projection(self.user)

        self.assertTrue(
            any(
                item["source"] == {"kind": "waitlist", "id": str(entry.pk)}
                and item["state"] == "waiting"
                and item["blocker"] is None
                for item in ongoing["items"]
            )
        )
        self.assertFalse(
            any(item["source"] == {"kind": "waitlist", "id": str(entry.pk)} for item in now["items"])
        )

        entry.status = WaitlistStatus.OFFERED
        entry.offered_order = self.owner_order
        entry.offered_at = timezone.now()
        entry.offer_expires_at = timezone.now() + timedelta(hours=2)
        entry.save(
            update_fields=[
                "status",
                "offered_order",
                "offered_at",
                "offer_expires_at",
                "updated_at",
            ]
        )

        offered_ongoing = build_personal_ongoing_projection(self.user)
        offered_now = build_personal_now_projection(self.user)

        self.assertTrue(
            any(item["source"] == {"kind": "waitlist", "id": str(entry.pk)} for item in offered_ongoing["items"])
        )
        decision = next(
            item for item in offered_now["items"]
            if item["source"] == {"kind": "waitlist", "id": str(entry.pk)}
        )
        self.assertEqual(decision["dimension"], "decision")
        self.assertEqual(decision["capabilities"], ["accept", "leave"])
