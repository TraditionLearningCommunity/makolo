import re

from django.contrib.auth import get_user_model
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase

from groups.models import GroupMembership
from groups.services import (
    accept_invitation,
    create_group,
    invite_member,
    request_invitation_email_verification,
    verify_invitation_email_identity,
)


User = get_user_model()
PASSWORD = "Password123!"


class InvitationIdentityVerificationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="identity-owner",
            email="identity-owner@example.com",
            password=PASSWORD,
        )
        self.other = User.objects.create_user(
            username="identity-other",
            email="identity-other@example.com",
            password=PASSWORD,
        )
        self.group = create_group(actor=self.owner, name="Groupe identité")

    def test_unknown_email_requires_secondary_verification_after_signup(self):
        invitation, token = invite_member(
            actor=self.owner,
            group=self.group,
            email="alice.new@example.com",
        )
        self.assertIsNone(invitation.profile_id)

        alice = User.objects.create_user(
            username="alice-new",
            email="alice.new@example.com",
            password=PASSWORD,
        )
        self.assertFalse(alice.email_verified)
        with self.assertRaises(PermissionDenied):
            accept_invitation(profile=alice, token=token)

        request_invitation_email_verification(profile=alice, token=token)
        self.assertEqual(len(mail.outbox), 2)
        challenge_email = mail.outbox[-1]
        self.assertEqual(challenge_email.to, ["alice.new@example.com"])
        match = re.search(r"Code de vérification : (\d{8})", challenge_email.body)
        self.assertIsNotNone(match)

        with self.assertRaises(ValidationError):
            verify_invitation_email_identity(profile=alice, token=token, code="00000000")

        verify_invitation_email_identity(profile=alice, token=token, code=match.group(1))
        alice.refresh_from_db()
        invitation.refresh_from_db()
        self.assertTrue(alice.email_verified)
        self.assertEqual(invitation.profile_id, alice.pk)

        accept_invitation(profile=alice, token=token)
        self.assertTrue(GroupMembership.objects.filter(group=self.group, profile=alice).exists())

    def test_transferred_link_cannot_request_challenge_for_wrong_profile(self):
        _, token = invite_member(
            actor=self.owner,
            group=self.group,
            email="unclaimed@example.com",
        )
        with self.assertRaises(PermissionDenied):
            request_invitation_email_verification(profile=self.other, token=token)
        with self.assertRaises(PermissionDenied):
            accept_invitation(profile=self.other, token=token)
