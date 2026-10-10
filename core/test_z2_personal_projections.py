from datetime import datetime, timedelta, timezone as datetime_timezone

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
        now_data = now_response.json()["data"]
        self.assertEqual(now_data["surface"], "now_me")
        self.assertEqual(now_data["actor"], {"type": "profile", "id": str(self.user.pk)})
        self.assertEqual(now_data["viewer"], now_data["actor"])
        self.assertEqual(now_data["items"], [])
        self.assertEqual(
            now_data["selection"],
            {"state": "empty", "reason": "no_current_attention_needed"},
        )
        self.assertEqual(now_data["actor_attention_state"], "calm")
        self.assertEqual(now_data["terminal"], {"state": "empty", "message": None})
        self.assertIsNone(now_data["continuation"])
        ongoing_data = ongoing_response.json()["data"]
        self.assertEqual(ongoing_data["surface"], "ongoing_me")
        self.assertEqual(
            ongoing_data["actor"],
            {"type": "profile", "id": str(self.user.pk)},
        )
        self.assertEqual(ongoing_data["viewer"], ongoing_data["actor"])
        self.assertEqual(ongoing_data["items"], [])
        self.assertEqual(
            ongoing_data["selection"],
            {"state": "empty", "reason": "no_personal_continuity"},
        )
        self.assertEqual(
            ongoing_data["terminal"],
            {"state": "empty", "message": None},
        )
        self.assertEqual(
            ongoing_data["continuation"],
            {"state": "end", "token": None},
        )
        self.assertEqual(ongoing_data["coverage_state"], "complete")
        self.assertNotIn("all_clear", now_data)
        self.assertEqual(now_response["Cache-Control"], "private, no-store")
        self.assertEqual(ongoing_response["Cache-Control"], "private, no-store")

    def test_ongoing_rejects_invalid_opaque_continuation(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("personal-projections:ongoing"),
            {"continuation": "not-a-valid-token"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("continuation", response.json())

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
        observed_at = datetime(2026, 10, 5, 12, 0, tzinfo=datetime_timezone.utc)
        step = JourneyStep.objects.create(
            journey=self.journey,
            title="Fournir l’attestation",
            position=10,
            is_required=True,
            due_at=observed_at + timedelta(days=7),
            created_by=self.user,
        )

        ongoing = build_personal_ongoing_projection(self.user, observed_at=observed_at)
        now = build_personal_now_projection(self.user, observed_at=observed_at)

        journey_item = next(
            item for item in ongoing["items"]
            if item["source"] == {"kind": "journey", "id": str(self.journey.pk)}
        )
        self.assertEqual(len(journey_item["actor_interventions"]), 1)
        self.assertEqual(journey_item["id"], journey_item["continuity_identity"])
        self.assertEqual(journey_item["continuity_basis"], [journey_item["source"]])
        self.assertEqual(journey_item["human_context"], self.activity.title)
        self.assertEqual(journey_item["synthesis"], journey_item["summary"])
        self.assertEqual(journey_item["where_i_am"], journey_item["summary"])
        self.assertEqual(journey_item["my_side"], journey_item["actor_interventions"])
        self.assertEqual(
            journey_item["profile_side_remaining"],
            [entry["title"] for entry in journey_item["actor_interventions"]],
        )
        self.assertEqual(journey_item["continues_elsewhere"], [])
        self.assertIsNone(journey_item["makolo_preparation"])
        self.assertEqual(journey_item["blockers"], [])
        self.assertEqual(
            ongoing["continuation"],
            {"state": "end", "token": None},
        )
        self.assertEqual(ongoing["coverage_state"], "complete")
        self.assertEqual(
            journey_item["knowledge_context"]["knowledge_state"],
            "known",
        )
        self.assertEqual(
            journey_item["handoffs"],
            [
                {
                    "type": "owner",
                    "target": "journey",
                    "id": str(self.journey.pk),
                }
            ],
        )
        self.assertFalse(
            any(
                item["source"] == {"kind": "journey", "id": str(self.journey.pk)}
                for item in now["items"]
            )
        )

        step.due_at = observed_at + timedelta(hours=1)
        step.save(update_fields=["due_at", "updated_at"])

        current = build_personal_now_projection(self.user, observed_at=observed_at)
        current_item = next(
            item
            for item in current["items"]
            if item["source"] == {"kind": "journey", "id": str(self.journey.pk)}
            and item["dimension"] == "action"
        )
        self.assertEqual(current_item["human_context"], self.activity.title)
        self.assertEqual(current_item["actionability"], "actionable")
        self.assertEqual(current["surface"], "now_me")
        self.assertEqual(current["selection"], {"state": "ready", "reason": None})
        self.assertEqual(current["actor_attention_state"], "active")
        self.assertEqual(current["terminal"], {"state": "ok", "message": None})
        self.assertEqual(current_item["id"], current_item["continuity_identity"])
        self.assertEqual(current_item["why_now"]["basis"], [current_item["source"]])
        self.assertEqual(current_item["why_now"]["meaning"], current_item["summary"])
        self.assertEqual(current_item["state_meaning"], current_item["summary"])
        self.assertEqual(current_item["consequence"]["target"], current_item["source"])
        self.assertEqual(current_item["consequence"]["state"], "unknown")
        self.assertIsNone(current_item["consequence"]["effect"])
        self.assertEqual(current_item["turn"], {"type": "profile"})
        self.assertEqual(current_item["response"]["type"], "act")
        self.assertEqual(
            current_item["horizon"]["state"],
            current_item["timing"]["deadline_state"],
        )
        self.assertEqual(
            current_item["owner_depth"]["links"]["detail"],
            f"/api/v1/me/journeys/{self.journey.pk}/",
        )
        self.assertEqual(current_item["knowledge_context"]["knowledge_state"], "known")
        self.assertEqual(current_item["attention"], {"level": "foreground"})
        self.assertEqual(
            current_item["handoffs"],
            [
                {
                    "type": "owner",
                    "target": "journey",
                    "id": str(self.journey.pk),
                }
            ],
        )
        self.assertEqual(
            current_item["links"]["web"],
            reverse("core:participant-journey-detail", kwargs={"pk": self.journey.pk}),
        )

        step.due_at = observed_at - timedelta(hours=1)
        step.save(update_fields=["due_at", "updated_at"])
        changed = build_personal_now_projection(self.user, observed_at=observed_at)
        changed_item = next(
            item
            for item in changed["items"]
            if item["source"] == {"kind": "journey", "id": str(self.journey.pk)}
        )
        self.assertEqual(changed_item["continuity_identity"], current_item["continuity_identity"])

        self.client.force_login(self.user)
        web = self.client.get(reverse("core:participant-home"))
        projected = [
            item
            for item in (
                web.context["home"].primary_attention,
                web.context["home"].primary_action,
                *web.context["home"].action_items,
            )
            if item is not None
        ]
        self.assertIn(
            current_item["human_context"],
            [item.context_label for item in projected],
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
        self.assertEqual(journey_item["summary"], "Cette démarche continue.")
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
        self.assertEqual(decision["turn"], {"type": "profile"})
        self.assertEqual(decision["response"]["type"], "decide")
        self.assertEqual(
            {action["capability"] for action in decision["business_actions"]},
            {"accept", "leave"},
        )
        self.assertEqual(
            {action["capability"]: action["label"] for action in decision["business_actions"]},
            {"accept": "Accepter", "leave": "Laisser passer"},
        )
        self.assertTrue(all(
            action["interaction_depth"] == "direct_now"
            and action["confirmation_required"] is True
            for action in decision["business_actions"]
        ))
