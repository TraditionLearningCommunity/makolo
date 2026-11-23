"""Owner-scoped Conversation participation inbox and lifecycle contracts."""
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from organizations.models import Organization

from .core_models import ConversationContextKind, ConversationLifecycle
from .participation_inbox import participation_inbox_for_profile
from .services import (
    create_conversation_invitation, ensure_context_conversation,
    respond_to_conversation_invitation, transition_conversation,
)

User = get_user_model()


class ParticipationInboxRegressionTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(
            username="participation-inbox-manager", password="StrongPass2026!",
        )
        self.invitee = User.objects.create_user(
            username="participation-inbox-invitee", password="StrongPass2026!",
        )
        self.outsider = User.objects.create_user(
            username="participation-inbox-outsider", password="StrongPass2026!",
        )
        self.space = Organization.objects.create(
            name="Participation Inbox", created_by=self.manager,
        )
        self.activity = Activity.objects.create(
            space=self.space, created_by=self.manager,
            title="Préparer la coordination",
        )
        grant_activity_role(
            profile=self.manager, activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.manager, source="participation-inbox-test",
        )
        self.conversation = ensure_context_conversation(
            actor=self.manager, kind=ConversationContextKind.ACTIVITY,
            activity=self.activity,
        )

    def test_sent_invitation_is_not_exposed_to_other_viewers(self):
        invitation = create_conversation_invitation(
            actor=self.manager, conversation=self.conversation,
            invitee=self.invitee,
        )
        self.assertEqual(
            [row["id"] for row in participation_inbox_for_profile(
                self.manager,
            )["sent_results"]],
            [str(invitation.pk)],
        )
        self.assertEqual(
            participation_inbox_for_profile(self.outsider)["sent_results"], [],
        )
        self.client.force_login(self.manager)
        response = self.client.get(
            reverse("conversations-api:invitation-list"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["sent_results"][0]["identifier"],
            self.invitee.username,
        )
        self.client.force_login(self.invitee)
        received = self.client.get(
            reverse("conversations-api:invitation-list"),
        )
        self.assertEqual(received.status_code, 200)
        self.assertEqual(len(received.json()["results"]), 1)
        self.assertEqual(received.json()["sent_results"], [])

    def test_closed_conversation_rejects_stale_invitation(self):
        invitation = create_conversation_invitation(
            actor=self.manager, conversation=self.conversation,
            invitee=self.invitee,
        )
        transition_conversation(
            actor=self.manager, conversation=self.conversation,
            lifecycle=ConversationLifecycle.CLOSED,
        )
        with self.assertRaises(ValidationError):
            respond_to_conversation_invitation(
                actor=self.invitee, invitation=invitation, accept=True,
            )
        self.client.force_login(self.invitee)
        response = self.client.get(
            reverse("conversations-api:invitation-list"),
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"], [])
        self.assertEqual(
            participation_inbox_for_profile(self.manager)["sent_results"], [],
        )
