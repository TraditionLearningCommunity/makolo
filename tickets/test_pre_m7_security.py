from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.test import TestCase

from .permissions import user_can_access_transfer, user_can_access_waitlist_entry


User = get_user_model()


class PreM7TicketPrivacyTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_user(
            username="pre-m7-ticket-staff",
            email="pre-m7-ticket-staff@example.com",
            is_staff=True,
        )
        self.owner = User.objects.create_user(
            username="pre-m7-ticket-owner",
            email="pre-m7-ticket-owner@example.com",
        )
        self.other = User.objects.create_user(
            username="pre-m7-ticket-other",
            email="pre-m7-ticket-other@example.com",
        )

    def test_simple_staff_cannot_read_waitlist_entry_without_contextual_authority(self):
        event = SimpleNamespace(activity=SimpleNamespace(space_id=None, owner_profile_id=self.owner.pk, created_by_id=self.owner.pk))
        entry = SimpleNamespace(user_id=self.owner.pk, ticket_type=SimpleNamespace(event=event))
        self.assertFalse(user_can_access_waitlist_entry(self.staff, entry))
        self.assertTrue(user_can_access_waitlist_entry(self.owner, entry))

    def test_simple_staff_cannot_read_transfer_without_contextual_authority(self):
        event = SimpleNamespace(activity=SimpleNamespace(space_id=None, owner_profile_id=self.owner.pk, created_by_id=self.owner.pk))
        transfer = SimpleNamespace(
            sender_id=self.owner.pk,
            recipient_id=self.other.pk,
            ticket=SimpleNamespace(event=event),
        )
        self.assertFalse(user_can_access_transfer(self.staff, transfer))
        self.assertTrue(user_can_access_transfer(self.owner, transfer))
        self.assertTrue(user_can_access_transfer(self.other, transfer))
