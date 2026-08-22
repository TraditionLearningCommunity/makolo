from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import OccurrenceStatus
from domain_events.contracts import DomainEventType
from domain_events.models import DomainEventOutbox
from operations.models import OperationsAuditLog
from organizations.services import create_organization

from .models import EventStatus, EventVisibility
from .services import complete_event, create_event, publish_event, reopen_event, update_event


User = get_user_model()


class CompletedEventEditingTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="lifecycle-owner",
            email="lifecycle-owner@makolo.test",
            password="Lifecycle-2026!",
        )
        self.outsider = User.objects.create_user(
            username="lifecycle-outsider",
            email="lifecycle-outsider@makolo.test",
            password="Lifecycle-2026!",
        )
        self.space = create_organization(
            creator=self.owner,
            name="Espace cycle de vie",
            country="CD",
            city="Lubumbashi",
        )

    def _published_event(self):
        start_at = timezone.now() + timedelta(days=7)
        event = create_event(
            actor=self.owner,
            organization=self.space,
            title="Événement cycle de vie",
            start_at=start_at,
            end_at=start_at + timedelta(hours=4),
            timezone="Africa/Lubumbashi",
            short_description="Description courte",
            description="Description initiale",
            visibility=EventVisibility.PUBLIC,
        )
        publish_event(event=event, actor=self.owner)
        return event

    def _prematurely_completed_event(self):
        event = self._published_event()
        complete_event(event=event, actor=self.owner)
        return event

    def test_published_event_edit_page_keeps_normal_schedule_fields(self):
        event = self._published_event()
        self.client.force_login(self.owner)

        response = self.client.get(reverse("events:edit", kwargs={"slug": event.slug}))

        self.assertEqual(response.status_code, 200)
        fields = response.context["form"].fields
        for field_name in {
            "organization",
            "venue",
            "start_at",
            "end_at",
            "registration_start_at",
            "registration_end_at",
            "timezone",
        }:
            self.assertIn(field_name, fields)

    def test_completed_event_edit_page_opens_and_only_exposes_editorial_fields(self):
        event = self._prematurely_completed_event()
        self.client.force_login(self.owner)

        response = self.client.get(reverse("events:edit", kwargs={"slug": event.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cet événement est terminé.")
        fields = response.context["form"].fields
        for field_name in {
            "organization",
            "venue",
            "start_at",
            "end_at",
            "registration_start_at",
            "registration_end_at",
            "timezone",
        }:
            self.assertNotIn(field_name, fields)
        for field_name in {"title", "short_description", "description", "category", "cover_image", "visibility"}:
            self.assertIn(field_name, fields)

    def test_editorial_update_keeps_completed_status_and_schedule(self):
        event = self._prematurely_completed_event()
        occurrence = event.primary_occurrence
        original_start = occurrence.start_at
        original_end = occurrence.end_at
        self.client.force_login(self.owner)

        response = self.client.post(
            reverse("events:edit", kwargs={"slug": event.slug}),
            {
                "title": "Titre corrigé après clôture",
                "short_description": "Résumé corrigé",
                "description": "Contenu éditorial corrigé sans rouvrir l’événement.",
                "visibility": EventVisibility.PUBLIC,
            },
        )

        self.assertRedirects(response, reverse("events:detail", kwargs={"slug": event.slug}))
        event.refresh_from_db()
        occurrence.refresh_from_db()
        self.assertEqual(event.title, "Titre corrigé après clôture")
        self.assertEqual(event.description, "Contenu éditorial corrigé sans rouvrir l’événement.")
        self.assertEqual(event.status, EventStatus.COMPLETED)
        self.assertEqual(occurrence.status, OccurrenceStatus.COMPLETED)
        self.assertEqual(occurrence.start_at, original_start)
        self.assertEqual(occurrence.end_at, original_end)

    def test_completed_event_schedule_cannot_be_changed_through_service(self):
        event = self._prematurely_completed_event()
        occurrence = event.primary_occurrence
        original_start = occurrence.start_at

        with self.assertRaises(ValidationError):
            update_event(
                event=event,
                actor=self.owner,
                start_at=original_start + timedelta(days=1),
            )

        occurrence.refresh_from_db()
        self.assertEqual(occurrence.start_at, original_start)
        self.assertEqual(occurrence.status, OccurrenceStatus.COMPLETED)

    def test_authorized_user_can_reopen_a_premature_completion_with_audit(self):
        event = self._prematurely_completed_event()
        occurrence = event.primary_occurrence
        event_id = event.pk
        activity_id = event.activity_id
        occurrence_id = occurrence.pk
        published_at = event.published_at

        reopened = reopen_event(event=event, actor=self.owner)

        reopened.refresh_from_db()
        occurrence.refresh_from_db()
        self.assertEqual(reopened.pk, event_id)
        self.assertEqual(reopened.activity_id, activity_id)
        self.assertEqual(occurrence.pk, occurrence_id)
        self.assertEqual(reopened.status, EventStatus.PUBLISHED)
        self.assertEqual(occurrence.status, OccurrenceStatus.SCHEDULED)
        self.assertEqual(reopened.published_at, published_at)
        self.assertTrue(
            DomainEventOutbox.objects.filter(
                event_type=DomainEventType.ACTIVITY_REOPENED,
                activity_id=activity_id,
            ).exists()
        )
        self.assertTrue(
            DomainEventOutbox.objects.filter(
                event_type=DomainEventType.OCCURRENCE_REOPENED,
                activity_id=activity_id,
            ).exists()
        )
        audit = OperationsAuditLog.objects.get(action="event.reopened", target_id=str(event_id))
        self.assertEqual(audit.actor, self.owner)
        self.assertEqual(audit.metadata["activity_id"], str(activity_id))
        self.assertEqual(audit.metadata["occurrence_id"], str(occurrence_id))

    def test_unauthorized_user_cannot_reopen_event(self):
        event = self._prematurely_completed_event()

        with self.assertRaises(PermissionDenied):
            reopen_event(event=event, actor=self.outsider)

        event.refresh_from_db()
        self.assertEqual(event.status, EventStatus.COMPLETED)
        self.assertFalse(OperationsAuditLog.objects.filter(action="event.reopened").exists())

    def test_past_completed_event_cannot_be_reopened(self):
        event = self._prematurely_completed_event()
        occurrence = event.primary_occurrence
        past_start = timezone.now() - timedelta(days=2)
        event.activity.occurrences.filter(pk=occurrence.pk).update(
            start_at=past_start,
            end_at=past_start + timedelta(hours=4),
        )
        occurrence.refresh_from_db()

        with self.assertRaises(ValidationError):
            reopen_event(event=event, actor=self.owner)

        event.refresh_from_db()
        occurrence.refresh_from_db()
        self.assertEqual(event.status, EventStatus.COMPLETED)
        self.assertEqual(occurrence.status, OccurrenceStatus.COMPLETED)

    def test_reopen_action_is_only_offered_for_future_completed_event(self):
        event = self._prematurely_completed_event()
        self.client.force_login(self.owner)

        response = self.client.get(reverse("events:detail", kwargs={"slug": event.slug}))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Réouvrir l’événement")

    def test_reopen_web_action_restores_event_and_occurrence(self):
        event = self._prematurely_completed_event()
        occurrence = event.primary_occurrence
        self.client.force_login(self.owner)

        response = self.client.post(reverse("events:reopen", kwargs={"slug": event.slug}))

        self.assertRedirects(response, reverse("events:detail", kwargs={"slug": event.slug}))
        event.refresh_from_db()
        occurrence.refresh_from_db()
        self.assertEqual(event.status, EventStatus.PUBLISHED)
        self.assertEqual(occurrence.status, OccurrenceStatus.SCHEDULED)
