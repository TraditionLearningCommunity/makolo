from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from authorization.constants import PermissionCode, SystemRoleCode
from authorization.services import can, grant_space_role
from discovery.presentation import build_discovery_item
from organizations.models import Organization

from .models import Event
from .selectors import get_public_discoverable_events
from .services import create_event, publish_event


User = get_user_model()


class Task24EventOwnershipTests(TestCase):
    def setUp(self):
        self.sarah = User.objects.create_user(
            username="task24-event-sarah",
            email="task24-event-sarah@example.test",
            first_name="Sarah",
            password="Task24-StrongPass!",
        )
        self.other = User.objects.create_user(
            username="task24-event-other",
            email="task24-event-other@example.test",
            first_name="Olivia",
            password="Task24-StrongPass!",
        )
        self.start = timezone.now() + timedelta(days=3)
        self.end = self.start + timedelta(hours=4)

    def test_personal_event_composes_personal_activity_without_fake_space(self):
        event = create_event(
            actor=self.sarah,
            organization=None,
            title="Mariage de Sarah",
            start_at=self.start,
            end_at=self.end,
            visibility="public",
        )
        activity = event.activity
        self.assertEqual(activity.owner_profile_id, self.sarah.pk)
        self.assertIsNone(activity.space_id)
        self.assertEqual(activity.created_by_id, self.sarah.pk)
        self.assertTrue(can(self.sarah, PermissionCode.ACTIVITY_MANAGE, activity=activity))
        self.assertFalse(can(self.other, PermissionCode.ACTIVITY_MANAGE, activity=activity))
        self.assertEqual(Organization.objects.count(), 0)

    def test_legacy_manager_new_personal_row_gets_explicit_owner(self):
        event = Event.objects.create(
            organizer=self.sarah,
            title="Compatibilité cérémonie",
            start_at=self.start,
            end_at=self.end,
        )
        self.assertEqual(event.activity.owner_profile_id, self.sarah.pk)
        self.assertEqual(event.activity.created_by_id, self.sarah.pk)
        self.assertIsNone(event.activity.space_id)

    def test_space_event_keeps_space_owner_and_human_provenance_distinct(self):
        space = Organization.objects.create(name="Makolo Beta Events", created_by=self.sarah)
        grant_space_role(
            profile=self.sarah,
            space=space,
            role=SystemRoleCode.SPACE_OWNER,
            granted_by=self.sarah,
            source="task24-test",
        )
        event = create_event(
            actor=self.sarah,
            organization=space,
            title="Forum Makolo",
            start_at=self.start,
            end_at=self.end,
        )
        self.assertEqual(event.activity.space_id, space.pk)
        self.assertIsNone(event.activity.owner_profile_id)
        self.assertEqual(event.activity.created_by_id, self.sarah.pk)

    def test_public_personal_event_uses_profile_operator_in_discovery(self):
        event = create_event(
            actor=self.sarah,
            title="Cérémonie publique",
            start_at=self.start,
            end_at=self.end,
            visibility="public",
        )
        publish_event(event=event, actor=self.sarah)
        self.assertTrue(get_public_discoverable_events().filter(pk=event.pk).exists())
        item = build_discovery_item(event.primary_occurrence)
        self.assertEqual(item.space_name, "Sarah")
