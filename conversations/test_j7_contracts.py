from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from domain_events.contracts import DomainEventType
from domain_events.models import DomainEventOutbox
from notifications.models import Notification
from organizations.models import Organization

from .audience_models import ConversationAudienceRuleKind, ConversationAudienceRuleOperation
from .audience_services import add_audience_rule, create_audience_set
from .core_models import ConversationContextKind, ConversationInvitationStatus
from .point_models import ConversationPointKind, ConversationPointResponseMode
from .point_services import create_point
from .services import (
    activate_participation,
    create_conversation_invitation,
    ensure_context_conversation,
    update_personal_conversation_state,
)


User = get_user_model()


class ConversationJ7ContractsTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="j7-contract-owner", email="j7-contract-owner@example.test", password="StrongPass2026!")
        self.member = User.objects.create_user(username="j7-contract-member", email="j7-contract-member@example.test", password="StrongPass2026!")
        self.outsider = User.objects.create_user(username="j7-contract-outsider", email="j7-contract-outsider@example.test", password="StrongPass2026!")
        self.space = Organization.objects.create(name="J7 Contract Space", created_by=self.owner)
        self.activity = Activity.objects.create(space=self.space, created_by=self.owner, title="J7 Contract Activity")
        grant_activity_role(
            profile=self.owner,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.owner,
            source="j7-conversations-contracts",
        )
        self.conversation = ensure_context_conversation(
            actor=self.owner,
            kind=ConversationContextKind.ACTIVITY,
            activity=self.activity,
        )
        activate_participation(actor=self.owner, conversation=self.conversation, profile=self.member)
        self.audience = create_audience_set(actor=self.owner, conversation=self.conversation, label="J7 Member")
        add_audience_rule(
            actor=self.owner,
            audience_set=self.audience,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.EXPLICIT_PROFILE,
            profile=self.member,
        )

    def _question(self, *, client_reference=None):
        return create_point(
            actor=self.owner,
            conversation=self.conversation,
            kind=ConversationPointKind.QUESTION,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            title="Texte privé à ne jamais copier dans un event",
            body="Contenu de coordination strictement privé",
            visibility_audience=self.audience,
            response_audience=self.audience,
            expected_action_audience=self.audience,
            client_reference=client_reference,
        )

    def test_point_event_payload_is_minimal_and_content_free(self):
        point = self._question()
        event = DomainEventOutbox.objects.filter(
            event_type=DomainEventType.CONVERSATION_POINT_PUBLISHED,
            source_id=str(point.pk),
        ).get()
        self.assertEqual(event.payload["point_id"], str(point.pk))
        self.assertEqual(event.payload["conversation_id"], str(self.conversation.pk))
        serialized = str(event.payload)
        self.assertNotIn(point.title, serialized)
        self.assertNotIn(point.body, serialized)

    def test_action_notification_is_created_after_commit_and_mute_is_respected(self):
        with self.captureOnCommitCallbacks(execute=True):
            point = self._question(client_reference="j7-notify-1")
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.member,
                metadata__conversation_id=str(self.conversation.pk),
            ).exists()
        )

        Notification.objects.filter(recipient=self.member).delete()
        update_personal_conversation_state(actor=self.member, conversation=self.conversation, mute=True)
        with self.captureOnCommitCallbacks(execute=True):
            self._question(client_reference="j7-notify-muted")
        self.assertFalse(Notification.objects.filter(recipient=self.member).exists())

    def test_api_hides_conversation_from_outsider(self):
        self.client.force_login(self.outsider)
        response = self.client.get(reverse("conversations-api:detail", kwargs={"pk": self.conversation.pk}))
        self.assertEqual(response.status_code, 404)

    def test_api_response_is_idempotent_by_client_reference(self):
        point = self._question(client_reference="j7-api-question")
        self.client.force_login(self.member)
        url = reverse("conversations-api:point-respond", kwargs={"point_pk": point.pk})
        first = self.client.post(
            url,
            {"value": "Réponse unique", "client_reference": "mobile-response-001"},
            content_type="application/json",
        )
        second = self.client.post(
            url,
            {"value": "Réponse unique", "client_reference": "mobile-response-001"},
            content_type="application/json",
        )
        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertEqual(point.responses.filter(actor=self.member).count(), 1)

    def test_invitation_grants_no_detail_access_until_accepted(self):
        invitation = create_conversation_invitation(
            actor=self.owner,
            conversation=self.conversation,
            invitee=self.outsider,
            client_reference="j7-invite-outsider",
        )
        self.client.force_login(self.outsider)
        detail_url = reverse("conversations-api:detail", kwargs={"pk": self.conversation.pk})
        self.assertEqual(self.client.get(detail_url).status_code, 404)

        invitation_list = self.client.get(reverse("conversations-api:invitation-list"))
        self.assertEqual(invitation_list.status_code, 200)
        self.assertEqual(invitation_list.json()["count"], 1)

        response = self.client.post(
            reverse("conversations-api:invitation-respond", kwargs={"invitation_pk": invitation.pk}),
            {"decision": "accept"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, ConversationInvitationStatus.ACCEPTED)
        self.assertEqual(self.client.get(detail_url).status_code, 200)

    def test_web_invitation_can_be_declined_without_revealing_detail(self):
        invitation = create_conversation_invitation(
            actor=self.owner,
            conversation=self.conversation,
            invitee=self.outsider,
            client_reference="j7-web-invite",
        )
        self.client.force_login(self.outsider)
        listing = self.client.get(reverse("conversations:list"))
        self.assertContains(listing, "Invitations")
        response = self.client.post(
            reverse("conversations:invitation-respond", kwargs={"invitation_pk": invitation.pk}),
            {"decision": "decline"},
        )
        self.assertRedirects(response, reverse("conversations:list"))
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, ConversationInvitationStatus.DECLINED)
