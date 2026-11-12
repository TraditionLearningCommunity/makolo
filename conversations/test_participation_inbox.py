"""Owner-scoped pending coordination and revocation regression contracts."""
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.urls import reverse

from groups.models import Group, GroupMembership, GroupMembershipStatus

from .core_models import (
    ConversationContextKind, ConversationEntryMode, ConversationJoinRequest,
    ConversationInvitation, ConversationInvitationStatus,
)
from .services import (
    create_conversation_invitation, create_join_request,
    ensure_context_conversation, respond_to_conversation_invitation,
    respond_to_join_request, transition_conversation,
    join_conversation,
)

User = get_user_model()


class ParticipationInboxTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="pending-manager", password="StrongPass2026!",
        )
        self.member = User.objects.create_user(
            username="pending-member", password="StrongPass2026!",
        )
        self.invitee = User.objects.create_user(
            username="pending-invitee", password="StrongPass2026!",
        )
        self.unrelated = User.objects.create_user(
            username="pending-unrelated", password="StrongPass2026!",
        )
        self.group = Group.objects.create(
            name="Collectif entrée", owner_profile=self.manager,
        )
        self.membership = GroupMembership.objects.create(
            group=self.group, profile=self.member,
        )
        self.conversation = ensure_context_conversation(
            actor=self.manager, kind=ConversationContextKind.GROUP,
            group=self.group, entry_mode=ConversationEntryMode.REQUEST,
        )
        self.invitation = create_conversation_invitation(
            actor=self.manager, conversation=self.conversation,
            invitee=self.invitee,
        )
        self.join_request = create_join_request(
            actor=self.member, conversation=self.conversation,
        )

    def _inbox(self, actor):
        self.client.force_login(actor)
        result = self.client.get(reverse("conversations-api:invitation-list"))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result["Cache-Control"], "private, no-store")
        return result.json()

    def test_owner_inbox_distinguishes_sent_received_and_join_requests(self):
        manager = self._inbox(self.manager)
        self.assertEqual(
            [item["id"] for item in manager["sent_results"]],
            [str(self.invitation.pk)],
        )
        self.assertEqual(manager["sent_results"][0]["identifier"], self.invitee.username)
        self.assertEqual(
            [item["id"] for item in manager["join_requests_to_decide"]],
            [str(self.join_request.pk)],
        )
        self.assertTrue(manager["join_requests_to_decide"][0]["can_approve"])
        self.assertEqual(manager["my_join_requests"], [])
        self.assertEqual(manager["results"], [])

        invitee = self._inbox(self.invitee)
        self.assertEqual(
            [item["id"] for item in invitee["results"]],
            [str(self.invitation.pk)],
        )
        self.assertEqual(invitee["sent_results"], [])
        self.assertEqual(invitee["join_requests_to_decide"], [])
        self.assertNotIn(self.member.username, str(invitee))

        member = self._inbox(self.member)
        self.assertEqual(
            [item["id"] for item in member["my_join_requests"]],
            [str(self.join_request.pk)],
        )
        self.assertEqual(member["join_requests_to_decide"], [])
        self.assertEqual(member["sent_results"], [])

        outsider = self._inbox(self.unrelated)
        self.assertEqual(outsider["sent_results"], [])
        self.assertEqual(outsider["join_requests_to_decide"], [])
        self.assertEqual(outsider["my_join_requests"], [])
        self.assertEqual(outsider["results"], [])

    def test_web_inbox_links_only_to_owner_managed_actions(self):
        self.client.force_login(self.manager)
        page = self.client.get(reverse("conversations:list"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Invitations envoyées")
        self.assertContains(page, "Demandes à examiner")
        self.assertContains(page, "Annuler l\'invitation")
        self.client.force_login(self.unrelated)
        outsider = self.client.get(reverse("conversations:list"))
        self.assertNotContains(outsider, self.member.username)
        self.assertNotContains(outsider, self.invitee.username)

    def test_revoked_context_blocks_approval_but_not_explicit_rejection(self):
        self.membership.status = GroupMembershipStatus.LEFT
        self.membership.save(update_fields=["status", "updated_at"])
        overview = self._inbox(self.manager)
        self.assertFalse(overview["join_requests_to_decide"][0]["can_approve"])
        with self.assertRaises(PermissionDenied):
            respond_to_join_request(
                actor=self.manager, join_request=self.join_request,
                approve=True,
            )
        self.join_request.refresh_from_db()
        self.assertEqual(self.join_request.status, "pending")
        result = respond_to_join_request(
            actor=self.manager, join_request=self.join_request,
            approve=False,
        )
        self.assertEqual(result.status, "rejected")

    def test_closed_conversation_cannot_admit_late_invitation_or_request(self):
        from .core_models import ConversationLifecycle
        transition_conversation(
            actor=self.manager, conversation=self.conversation,
            lifecycle=ConversationLifecycle.CLOSED,
        )
        with self.assertRaises(ValidationError):
            respond_to_conversation_invitation(
                actor=self.invitee, invitation=self.invitation, accept=True,
            )
        with self.assertRaises(ValidationError):
            respond_to_join_request(
                actor=self.manager, join_request=self.join_request,
                approve=True,
            )
        with self.assertRaises(ValidationError):
            create_join_request(
                actor=self.member, conversation=self.conversation,
                client_reference="late-request",
            )
        self.invitation.refresh_from_db()
        self.join_request.refresh_from_db()
        self.assertEqual(self.invitation.status, ConversationInvitationStatus.PENDING)
        self.assertEqual(self.join_request.status, "pending")

        self.conversation.refresh_from_db()
        self.conversation.entry_mode = ConversationEntryMode.JOIN
        self.conversation.save(update_fields=["entry_mode", "updated_at"])
        with self.assertRaises(ValidationError):
            join_conversation(actor=self.member, conversation=self.conversation)

    def test_pending_request_from_other_group_is_not_in_manager_inbox(self):
        other_group = Group.objects.create(
            name="Collectif isolé", owner_profile=self.unrelated,
        )
        GroupMembership.objects.create(group=other_group, profile=self.member)
        other = ensure_context_conversation(
            actor=self.unrelated, kind=ConversationContextKind.GROUP,
            group=other_group, entry_mode=ConversationEntryMode.REQUEST,
        )
        other_request = create_join_request(
            actor=self.member, conversation=other,
        )
        manager = self._inbox(self.manager)
        self.assertNotIn(str(other_request.pk), str(manager["join_requests_to_decide"]))
        unrelated = self._inbox(self.unrelated)
        self.assertIn(
            str(other_request.pk),
            [item["id"] for item in unrelated["join_requests_to_decide"]],
        )
