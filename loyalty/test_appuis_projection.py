"""Regression checks for the existing Loyalty membership owner handoff."""
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from django.test import SimpleTestCase

from loyalty.api.views import _personal_membership_payload
from loyalty.models import MembershipStatus


class PersonalMembershipHandoffTests(SimpleTestCase):
    def _projection(self, status):
        membership = SimpleNamespace(pk=uuid4(), status=status)
        with patch("loyalty.api.views.MembershipSubscriptionSerializer") as serializer:
            serializer.return_value.data = {"id": str(membership.pk), "status": status}
            return membership, _personal_membership_payload(membership)

    def test_active_member_receives_owner_cancel_action(self):
        membership, payload = self._projection(MembershipStatus.ACTIVE)
        self.assertEqual(payload["capabilities"], ["cancel"])
        self.assertEqual(
            payload["links"]["cancel"],
            f"/api/v1/loyalty/memberships/{membership.pk}/cancel/",
        )

    def test_pending_member_receives_owner_cancel_action(self):
        _membership, payload = self._projection(MembershipStatus.PENDING)
        self.assertEqual(payload["capabilities"], ["cancel"])

    def test_finished_member_has_no_mutation_capability(self):
        for status in (MembershipStatus.EXPIRED, MembershipStatus.CANCELLED):
            with self.subTest(status=status):
                _membership, payload = self._projection(status)
                self.assertEqual(payload["capabilities"], [])
                self.assertEqual(payload["links"], {})
