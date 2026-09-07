from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import TestCase

from activities.models import Activity
from notifications.models import Notification
from organizations.models import Organization

from .audience_models import ConversationAudienceRuleKind, ConversationAudienceRuleOperation
from .audience_services import add_audience_rule, create_audience_set
from .core_models import ConversationContextKind
from .moderation_services import moderate_exchange_entry
from .point_models import (
    ConversationExchangeModerationState,
    ConversationPointKind,
    ConversationPointResponseMode,
)
from .point_services import close_point_responses, create_exchange_entry, create_point
from .services import activate_participation, ensure_context_conversation


User = get_user_model()


class ConversationEscalationAndModerationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="j7-hardening-owner",
            email="j7-hardening-owner@example.test",
            password="StrongPass2026!",
        )
        self.member = User.objects.create_user(
            username="j7-hardening-member",
            email="j7-hardening-member@example.test",
            password="StrongPass2026!",
        )
        self.outsider = User.objects.create_user(
            username="j7-hardening-outsider",
            email="j7-hardening-outsider@example.test",
            password="StrongPass2026!",
        )
        self.space = Organization.objects.create(name="J7 Hardening Space", created_by=self.owner)
        self.activity = Activity.objects.create(
            space=self.space,
            owner_profile=self.owner,
            created_by=self.owner,
            title="J7 Hardening Activity",
        )
        self.conversation = ensure_context_conversation(
            actor=self.owner,
            kind=ConversationContextKind.ACTIVITY,
            activity=self.activity,
        )
        activate_participation(actor=self.owner, conversation=self.conversation, profile=self.member)
        self.member_audience = create_audience_set(
            actor=self.owner,
            conversation=self.conversation,
            label="Membre attendu",
        )
        add_audience_rule(
            actor=self.owner,
            audience_set=self.member_audience,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.EXPLICIT_PROFILE,
            profile=self.member,
        )

    def test_response_close_escalates_only_to_manager_when_action_is_missing(self):
        point = create_point(
            actor=self.owner,
            conversation=self.conversation,
            kind=ConversationPointKind.QUESTION,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            title="Réponse attendue",
            response_audience=self.member_audience,
            expected_action_audience=self.member_audience,
        )
        Notification.objects.all().delete()

        with self.captureOnCommitCallbacks(execute=True):
            close_point_responses(actor=self.owner, point=point)

        self.assertTrue(
            Notification.objects.filter(
                recipient=self.owner,
                template_key="conversation.point.escalation",
            ).exists()
        )
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.member,
                template_key="conversation.point.escalation",
            ).exists()
        )

    def test_exchange_moderation_requires_current_moderation_authority(self):
        point = create_point(
            actor=self.owner,
            conversation=self.conversation,
            kind=ConversationPointKind.EXCHANGE,
            response_mode=ConversationPointResponseMode.FREE_TEXT,
            title="Coordination libre",
            visibility_audience=self.member_audience,
            response_audience=self.member_audience,
        )
        entry = create_exchange_entry(actor=self.member, point=point, body="Une précision utile")

        with self.assertRaises(PermissionDenied):
            moderate_exchange_entry(
                actor=self.outsider,
                entry=entry,
                state=ConversationExchangeModerationState.HIDDEN,
            )

        moderated = moderate_exchange_entry(
            actor=self.owner,
            entry=entry,
            state=ConversationExchangeModerationState.REMOVED,
        )
        self.assertEqual(moderated.moderation_state, ConversationExchangeModerationState.REMOVED)
        self.assertEqual(moderated.removed_by_id, self.owner.pk)
        self.assertIsNotNone(moderated.removed_at)
