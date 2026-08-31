from django.contrib.auth import get_user_model
from django.test import TestCase

from domain_events.contracts import DomainEventType
from domain_events.services import emit_domain_event
from organizations.models import Organization

from .domain_event_consumer import consume_analytics_event
from .models import AnalyticsFact


User = get_user_model()


class SubscriptionAnalyticsFactTests(TestCase):
    def test_profile_subscription_event_projects_minimal_idempotent_fact(self):
        profile = User.objects.create_user(
            username="analytics-s6-profile",
            email="analytics-s6-profile@example.test",
            password="test-only",
        )
        event = emit_domain_event(
            event_type=DomainEventType.SUBSCRIPTION_TRANSITION_COMPLETED,
            source_type="subscription",
            source_id="subscription-test",
            idempotency_key="analytics-s6-profile-transition",
            payload={
                "subscription_id": "subscription-test",
                "subject_type": "profile",
                "subject_id": str(profile.pk),
                "transition_kind": "base_switch",
                "new_state": "completed",
            },
            process_on_commit=False,
        )
        consume_analytics_event(event)
        consume_analytics_event(event)
        facts = AnalyticsFact.objects.filter(
            domain_event=event,
            fact_type=DomainEventType.SUBSCRIPTION_TRANSITION_COMPLETED,
        )
        self.assertEqual(facts.count(), 1)
        fact = facts.get()
        self.assertEqual(fact.profile, profile)
        self.assertIsNone(fact.space)
        self.assertIsNone(fact.numeric_value)
        self.assertEqual(fact.currency, "")

    def test_space_subscription_event_projects_space_without_requirement_payload(self):
        owner = User.objects.create_user(
            username="analytics-s6-owner",
            email="analytics-s6-owner@example.test",
            password="test-only",
        )
        space = Organization.objects.create(name="Analytics S6 Space", created_by=owner)
        event = emit_domain_event(
            event_type=DomainEventType.SUBSCRIPTION_SUSPENDED,
            source_type="subscription",
            source_id="subscription-space-test",
            space_id=space.pk,
            idempotency_key="analytics-s6-space-suspended",
            payload={
                "subscription_id": "subscription-space-test",
                "subject_type": "space",
                "subject_id": str(space.pk),
                "new_state": "suspended",
            },
            process_on_commit=False,
        )
        consume_analytics_event(event)
        fact = AnalyticsFact.objects.get(
            domain_event=event,
            fact_type=DomainEventType.SUBSCRIPTION_SUSPENDED,
        )
        self.assertEqual(fact.space, space)
        self.assertIsNone(fact.profile)
