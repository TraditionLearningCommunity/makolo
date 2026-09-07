from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity
from organizations.models import Organization

from .automation import process_due_conversation_points
from .core_models import ConversationContextKind
from .point_models import (
    ConversationPointKind,
    ConversationPointLifecycle,
    ConversationPointResolutionPolicy,
    ConversationPointResponseMode,
)
from .point_services import create_point, submit_point_response
from .services import ensure_context_conversation


User = get_user_model()


class ConversationAutomationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="j7-owner", email="j7-owner@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="J7 Space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="J7 Activity")
        self.conversation = ensure_context_conversation(actor=self.owner, kind=ConversationContextKind.ACTIVITY, activity=self.activity)

    def test_deadline_closes_responses_idempotently(self):
        now = timezone.now()
        point = create_point(
            actor=self.owner,
            conversation=self.conversation,
            kind=ConversationPointKind.QUESTION,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            title="Question limitée",
            opens_at=now - timedelta(hours=2),
            deadline_at=now - timedelta(hours=1),
        )
        first = process_due_conversation_points(now=now)
        point.refresh_from_db()
        self.assertEqual(point.lifecycle, ConversationPointLifecycle.RESPONSE_CLOSED)
        self.assertEqual(first["responses_closed"], 1)
        second = process_due_conversation_points(now=now)
        self.assertEqual(second["examined"], 0)

    def test_valid_until_expires_point(self):
        now = timezone.now()
        point = create_point(
            actor=self.owner,
            conversation=self.conversation,
            kind=ConversationPointKind.INFORMATION,
            title="Information temporaire",
            opens_at=now - timedelta(hours=2),
            valid_until=now - timedelta(hours=1),
        )
        stats = process_due_conversation_points(now=now)
        point.refresh_from_db()
        self.assertEqual(point.lifecycle, ConversationPointLifecycle.EXPIRED)
        self.assertIsNotNone(point.expired_at)
        self.assertEqual(stats["expired"], 1)

    def test_plurality_resolves_only_when_deadline_closes_responses(self):
        now = timezone.now()
        point = create_point(
            actor=self.owner,
            conversation=self.conversation,
            kind=ConversationPointKind.POLL,
            response_mode=ConversationPointResponseMode.SINGLE_CHOICE,
            resolution_policy=ConversationPointResolutionPolicy.PLURALITY,
            title="Choisir une option",
            opens_at=now - timedelta(hours=1),
            deadline_at=now + timedelta(hours=1),
            options=("A", "B"),
        )
        first_option = point.options.order_by("position").first()
        submit_point_response(actor=self.owner, point=point, value=str(first_option.pk))
        point.refresh_from_db()
        self.assertEqual(point.lifecycle, ConversationPointLifecycle.OPEN)

        stats = process_due_conversation_points(now=now + timedelta(hours=2))
        point.refresh_from_db()
        self.assertEqual(point.lifecycle, ConversationPointLifecycle.RESOLVED)
        self.assertEqual(stats["responses_closed"], 1)
        self.assertEqual(stats["resolved"], 1)
