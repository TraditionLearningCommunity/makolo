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
    join_conversation, withdraw_join_request,
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
        self.assertEqual(invitee["results"][0]["invited_by"], self.manager.username)
        self.assertEqual(invitee["results"][0]["context_kind"], "group")
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

    def test_received_invitations_report_a_bounded_window(self):
        second_group = Group.objects.create(
            name="Autre coordination", owner_profile=self.manager,
        )
        second_conversation = ensure_context_conversation(
            actor=self.manager, kind=ConversationContextKind.GROUP,
            group=second_group,
        )
        create_conversation_invitation(
            actor=self.manager, conversation=second_conversation,
            invitee=self.invitee,
        )
        self.client.force_login(self.invitee)
        response = self.client.get(
            reverse("conversations-api:invitation-list"),
            {"limit": 1},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["count"], 1)
        self.assertTrue(payload["more_received"])
        self.assertEqual(len(payload["results"]), 1)
        self.assertIn("more_collective", payload)
        self.assertNotIn("password", str(payload))

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

    def test_invitation_cannot_transfer_space_representation(self):
        from organizations.models import Organization
        space = Organization.objects.create(
            name="Espace sans mandat", created_by=self.manager,
        )
        self.invitation.represented_space = space
        self.invitation.save(update_fields=["represented_space", "updated_at"])
        received = self._inbox(self.invitee)
        self.assertFalse(received["results"][0]["can_accept"])
        with self.assertRaises(ValidationError):
            respond_to_conversation_invitation(
                actor=self.invitee, invitation=self.invitation, accept=True,
            )
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, "pending")

    def test_changed_contact_policy_withdraws_acceptance_without_erasing_invitation(self):
        from .contact_models import ProfileContactPolicy, ContactPolicyMode
        ProfileContactPolicy.objects.create(
            profile=self.invitee, mode=ContactPolicyMode.CLOSED,
        )
        received = self._inbox(self.invitee)
        self.assertEqual(len(received["results"]), 1)
        self.assertFalse(received["results"][0]["can_accept"])
        with self.assertRaises(ValidationError):
            respond_to_conversation_invitation(
                actor=self.invitee, invitation=self.invitation, accept=True,
            )
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, ConversationInvitationStatus.PENDING)
        declined = respond_to_conversation_invitation(
            actor=self.invitee, invitation=self.invitation, accept=False,
        )
        self.assertEqual(declined.status, ConversationInvitationStatus.DECLINED)

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

    def test_join_requests_expose_handle_not_private_full_name(self):
        self.member.first_name = "Nom"
        self.member.last_name = "Confidentiel"
        self.member.save(update_fields=["first_name", "last_name"])
        self.client.force_login(self.manager)
        endpoint = reverse(
            "conversations-api:join-requests",
            kwargs={"pk": self.conversation.pk},
        )
        response = self.client.get(endpoint)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["label"], self.member.username)
        self.assertNotIn("Confidentiel", str(response.json()))
        page = self.client.get(reverse(
            "conversations:participants",
            kwargs={"pk": self.conversation.pk},
        ))
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Nom Confidentiel")
        self.assertContains(page, "@" + self.member.username)

    def test_inactive_requester_cannot_gain_access_from_pending_decision(self):
        self.member.is_active = False
        self.member.save(update_fields=["is_active"])
        overview = self._inbox(self.manager)
        self.assertFalse(overview["join_requests_to_decide"][0]["can_approve"])
        with self.assertRaises(PermissionDenied):
            respond_to_join_request(
                actor=self.manager, join_request=self.join_request,
                approve=True,
            )
        self.join_request.refresh_from_db()
        self.assertEqual(self.join_request.status, "pending")

    def test_expired_invitation_becomes_terminal_without_admission(self):
        from datetime import timedelta
        from django.utils import timezone
        self.invitation.expires_at = timezone.now() - timedelta(seconds=1)
        self.invitation.save(update_fields=["expires_at", "updated_at"])
        self.client.force_login(self.invitee)
        endpoint = reverse(
            "conversations-api:invitation-respond",
            kwargs={"invitation_pk": self.invitation.pk},
        )
        result = self.client.post(
            endpoint, {"decision": "accept"},
            content_type="application/json",
        )
        self.assertEqual(result.status_code, 409)
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, "expired")
        self.assertEqual(self._inbox(self.invitee)["results"], [])

    def test_approved_request_cannot_be_silently_rejected_by_second_manager_action(self):
        respond_to_join_request(
            actor=self.manager, join_request=self.join_request,
            approve=True,
        )
        self.client.force_login(self.manager)
        endpoint = reverse(
            "conversations-api:join-decision",
            kwargs={
                "pk": self.conversation.pk,
                "join_request_pk": self.join_request.pk,
            },
        )
        conflict = self.client.post(
            endpoint, {"decision": "reject"},
            content_type="application/json",
        )
        self.assertEqual(conflict.status_code, 409)
        self.join_request.refresh_from_db()
        self.assertEqual(self.join_request.status, "approved")

    def test_declined_invitation_never_acknowledges_a_late_acceptance(self):
        respond_to_conversation_invitation(
            actor=self.invitee, invitation=self.invitation, accept=False,
        )
        self.client.force_login(self.invitee)
        endpoint = reverse(
            "conversations-api:invitation-respond",
            kwargs={"invitation_pk": self.invitation.pk},
        )
        conflict = self.client.post(
            endpoint, {"decision": "accept"},
            content_type="application/json",
        )
        self.assertEqual(conflict.status_code, 409)
        self.invitation.refresh_from_db()
        self.assertEqual(self.invitation.status, "declined")

    def test_requester_withdraws_pending_request_without_conversation_access(self):
        self.membership.status = GroupMembershipStatus.LEFT
        self.membership.save(update_fields=["status", "updated_at"])
        self.client.force_login(self.member)
        url = reverse(
            "conversations-api:join-withdraw",
            kwargs={"join_request_pk": self.join_request.pk},
        )
        result = self.client.post(url)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["id"], str(self.join_request.pk))
        self.assertEqual(result.json()["status"], "cancelled")
        self.assertEqual(self.client.post(url).json()["status"], "cancelled")
        self.join_request.refresh_from_db()
        self.assertEqual(self.join_request.status, "cancelled")
        self.assertEqual(self._inbox(self.member)["my_join_requests"], [])

        manager = self._inbox(self.manager)
        self.assertEqual(manager["join_requests_to_decide"], [])
        self.client.force_login(self.unrelated)
        self.assertEqual(self.client.post(url).status_code, 404)

    def test_withdrawal_never_cancels_approved_participation(self):
        respond_to_join_request(
            actor=self.manager, join_request=self.join_request,
            approve=True,
        )
        self.client.force_login(self.member)
        url = reverse(
            "conversations-api:join-withdraw",
            kwargs={"join_request_pk": self.join_request.pk},
        )
        self.assertEqual(self.client.post(url).status_code, 400)
        self.join_request.refresh_from_db()
        self.assertEqual(self.join_request.status, "approved")
        from .core_models import ConversationParticipation
        self.assertTrue(ConversationParticipation.objects.filter(
            conversation=self.conversation, profile=self.member,
            status="active",
        ).exists())

    def test_web_requester_can_withdraw_with_csrf_post(self):
        self.client.force_login(self.member)
        page = self.client.get(reverse("conversations:list"))
        self.assertContains(page, "Retirer ma demande")
        url = reverse(
            "conversations:join-withdraw",
            kwargs={"join_request_pk": self.join_request.pk},
        )
        response = self.client.post(url)
        self.assertEqual(response.status_code, 302)
        self.join_request.refresh_from_db()
        self.assertEqual(self.join_request.status, "cancelled")

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
