"""Lot 7: cross-lot contracts over existing owners and permission boundaries.

These are targeted regression tests, not new business models or a replacement
for the mobile/Web smoke tests. In particular, unread != actionable attention
and collective consent != explicit participation.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from groups.models import Group, GroupDiscoverability, GroupMembership
from notifications.models import Notification
from organizations.models import Organization

from .attention import (
    conversation_attention_badge_count,
    has_conversation_attention,
    point_attention_reason,
)
from .attention_projection import conversation_attention_sections
from .audience_models import (
    ConversationAudienceRuleKind, ConversationAudienceRuleOperation,
)
from .audience_services import add_audience_rule, create_audience_set
from .core_models import (
    ConversationContextKind, ConversationHistoryPolicy,
    ConversationParticipation, ConversationParticipationStatus,
)
from .participant_services import (
    answer_collective_invitation, invite_identifier, revoke_collective_access,
)
from .point_interactions import point_interactions_for_profile
from .point_models import ConversationPointKind, ConversationPointResponseMode
from .point_services import create_point, point_visible_to, submit_point_response
from .services import (
    activate_participation, can_view_conversation, ensure_context_conversation,
    remove_participation,
)

User = get_user_model()


class Lot7AttentionContractTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="lot7-attn-manager", password="StrongPass2026!")
        self.member = User.objects.create_user(username="lot7-attn-member", password="StrongPass2026!")
        self.outsider = User.objects.create_user(username="lot7-attn-outsider", password="StrongPass2026!")
        self.space = Organization.objects.create(name="Lot7 Attention", created_by=self.manager)
        self.activity = Activity.objects.create(
            space=self.space, created_by=self.manager, title="Coordination Lot7",
        )
        grant_activity_role(
            profile=self.manager, activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.manager, source="lot7-attention",
        )
        self.conversation = ensure_context_conversation(
            actor=self.manager, kind=ConversationContextKind.ACTIVITY,
            activity=self.activity,
        )
        activate_participation(
            actor=self.manager, conversation=self.conversation,
            profile=self.member,
        )
        self.audience = create_audience_set(
            actor=self.manager, conversation=self.conversation,
            label="Seul le membre attendu",
        )
        add_audience_rule(
            actor=self.manager, audience_set=self.audience,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.EXPLICIT_PROFILE,
            profile=self.member,
        )

    def question(self, **kwargs):
        return create_point(
            actor=self.manager, conversation=self.conversation,
            kind=ConversationPointKind.QUESTION,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            title="Coordination ciblée",
            visibility_audience=self.audience,
            response_audience=self.audience,
            expected_action_audience=self.audience,
            **kwargs,
        )

    def test_attention_disappears_after_authoritative_response_and_outsider_never_sees(self):
        point = self.question()
        self.assertEqual(point_attention_reason(self.member, point), "respond")
        self.assertTrue(has_conversation_attention(self.member))
        self.assertEqual(conversation_attention_badge_count(self.member), 1)
        self.assertIsNone(point_attention_reason(self.outsider, point))
        self.assertFalse(point_visible_to(self.outsider, point))
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(
            reverse("conversations-api:attention", kwargs={"pk": self.conversation.pk}),
        ).status_code, 404)
        self.client.force_login(self.member)
        submit_point_response(
            actor=self.member, point=point, value="Réponse ferme",
            client_reference="lot7-response-confirmed",
        )
        self.assertIsNone(point_attention_reason(self.member, point))
        self.assertFalse(has_conversation_attention(self.member))
        lens = conversation_attention_sections(self.member, self.conversation)
        self.assertTrue(lens["all_clear"])
        self.assertEqual(lens["action_count"], 0)

    def test_future_question_is_knowledge_not_an_urgent_action(self):
        point = self.question(opens_at=timezone.now() + timedelta(days=1))
        self.assertIsNone(point_attention_reason(self.member, point))
        self.assertFalse(has_conversation_attention(self.member))
        lens = conversation_attention_sections(self.member, self.conversation)
        self.assertEqual(lens["action_count"], 0)
        item = next(row for row in lens["to_know"] if row["id"] == str(point.pk))
        self.assertEqual(item["reason"], "upcoming")
        self.assertFalse(item["actionable"])

    def test_acknowledgement_before_opening_is_denied_on_server(self):
        point = create_point(
            actor=self.manager, conversation=self.conversation,
            kind=ConversationPointKind.INFORMATION,
            title="Lecture planifiée", requires_acknowledgement=True,
            visibility_audience=self.audience,
            expected_action_audience=self.audience,
            opens_at=timezone.now() + timedelta(hours=3),
        )
        self.assertFalse(
            point_interactions_for_profile(self.member, point)["can_acknowledge"],
        )
        self.client.force_login(self.member)
        response = self.client.post(
            reverse("conversations-api:point-acknowledge", kwargs={"point_pk": point.pk}),
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(point.user_states.filter(
            profile=self.member, acknowledged_at__isnull=False,
        ).exists())

    def test_revisit_is_personal_and_revocation_rechecks_access(self):
        point = create_point(
            actor=self.manager, conversation=self.conversation,
            kind=ConversationPointKind.INFORMATION,
            title="Note à retrouver",
        )
        self.client.force_login(self.member)
        url = reverse("conversations-api:point-personal-state", kwargs={"point_pk": point.pk})
        updated = self.client.post(url, {"revisit": True}, content_type="application/json")
        self.assertEqual(updated.status_code, 200)
        self.assertTrue(updated.json()["revisit"])
        self.assertEqual(point.lifecycle, "open")
        self.assertFalse(point.user_states.filter(profile=self.manager).exists())
        lens = conversation_attention_sections(self.member, self.conversation)
        self.assertIn(str(point.pk), [row["id"] for row in lens["to_know"]])
        self.assertEqual(lens["action_count"], 0)

        participation = ConversationParticipation.objects.get(
            conversation=self.conversation, profile=self.member,
            status=ConversationParticipationStatus.ACTIVE,
        )
        remove_participation(actor=self.manager, participation=participation)
        self.assertFalse(can_view_conversation(self.member, self.conversation))
        self.assertEqual(conversation_attention_sections(
            self.member, self.conversation,
        )["to_know"], [])
        self.assertEqual(self.client.post(
            url, {"revisit": False}, content_type="application/json",
        ).status_code, 404)


class Lot7CollectiveConsentTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="lot7-group-manager", password="StrongPass2026!")
        self.representative = User.objects.create_user(username="lot7-group-owner", password="StrongPass2026!")
        self.member = User.objects.create_user(username="lot7-group-member", password="StrongPass2026!")
        self.space = Organization.objects.create(name="Lot7 Group Context", created_by=self.manager)
        self.activity = Activity.objects.create(
            space=self.space, created_by=self.manager, title="Lot7 Group Activity",
        )
        grant_activity_role(
            profile=self.manager, activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
            granted_by=self.manager, source="lot7-collective",
        )
        self.conversation = ensure_context_conversation(
            actor=self.manager, kind=ConversationContextKind.ACTIVITY,
            activity=self.activity,
        )
        self.conversation.history_policy = ConversationHistoryPolicy.FROM_JOIN
        self.conversation.save(update_fields=["history_policy", "updated_at"])
        self.group = Group.objects.create(
            name="Collectif disponible Lot7",
            owner_profile=self.representative,
            discoverability=GroupDiscoverability.LISTED,
        )

    def test_collective_requires_acceptance_and_membership_is_dynamic(self):
        old_point = create_point(
            actor=self.manager, conversation=self.conversation,
            kind=ConversationPointKind.INFORMATION,
            title="Avant admission",
        )
        with self.assertRaises(ValidationError):
            invite_identifier(
                actor=self.manager, conversation=self.conversation,
                kind="group", identifier=self.group.name,
            )
        kind, access = invite_identifier(
            actor=self.manager, conversation=self.conversation,
            kind="group", identifier=self.group.slug,
        )
        self.assertEqual(kind, "group")
        self.assertEqual(access.status, "pending")
        self.assertFalse(can_view_conversation(self.representative, self.conversation))
        self.assertFalse(ConversationParticipation.objects.filter(
            conversation=self.conversation, profile=self.representative,
        ).exists())

        answered = answer_collective_invitation(
            actor=self.representative, access=access, accept=True,
        )
        self.assertEqual(answered.status, "active")
        self.assertTrue(can_view_conversation(self.representative, self.conversation))
        self.assertFalse(point_visible_to(self.representative, old_point))
        self.assertFalse(ConversationParticipation.objects.filter(
            conversation=self.conversation, profile=self.representative,
        ).exists())

        new_point = create_point(
            actor=self.manager, conversation=self.conversation,
            kind=ConversationPointKind.INFORMATION, title="Après admission",
        )
        self.assertTrue(point_visible_to(self.representative, new_point))
        self.assertFalse(can_view_conversation(self.member, self.conversation))
        membership = GroupMembership.objects.create(
            group=self.group, profile=self.member,
        )
        self.assertTrue(can_view_conversation(self.member, self.conversation))
        self.assertTrue(point_visible_to(self.member, new_point))
        membership.status = "left"
        membership.save(update_fields=["status", "updated_at"])
        self.assertFalse(can_view_conversation(self.member, self.conversation))

        revoke_collective_access(actor=self.manager, access=answered)
        self.assertFalse(can_view_conversation(self.representative, self.conversation))
        self.assertFalse(ConversationParticipation.objects.filter(
            conversation=self.conversation, profile=self.representative,
        ).exists())
