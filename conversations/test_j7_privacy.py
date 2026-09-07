from django.contrib.auth import get_user_model
from django.test import TestCase

from activities.models import Activity
from notifications.models import Notification
from organizations.models import Organization

from .audience_models import ConversationAudienceRuleKind, ConversationAudienceRuleOperation
from .audience_services import add_audience_rule, create_audience_set
from .contact_models import ContactPolicyMode, ProfileContactPolicy
from .contact_services import ensure_direct_conversation
from .core_models import ConversationContext, ConversationContextKind
from .point_models import ConversationPointKind, ConversationPointResponseMode
from .point_services import create_point, point_visible_to
from .services import activate_participation, ensure_context_conversation


User = get_user_model()


class ConversationNotificationPrivacyTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="j7-privacy-owner",
            email="j7-privacy-owner@example.test",
            password="StrongPass2026!",
        )
        self.visible = User.objects.create_user(
            username="j7-privacy-visible",
            email="j7-privacy-visible@example.test",
            password="StrongPass2026!",
        )
        self.hidden = User.objects.create_user(
            username="j7-privacy-hidden",
            email="j7-privacy-hidden@example.test",
            password="StrongPass2026!",
        )
        self.space = Organization.objects.create(name="J7 Privacy Space", created_by=self.owner)
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title="J7 Privacy Activity",
        )
        self.conversation = ensure_context_conversation(
            actor=self.owner,
            kind=ConversationContextKind.ACTIVITY,
            activity=self.activity,
        )
        activate_participation(actor=self.owner, conversation=self.conversation, profile=self.visible)
        activate_participation(actor=self.owner, conversation=self.conversation, profile=self.hidden)

    def _audience(self, *, label, profile):
        audience = create_audience_set(actor=self.owner, conversation=self.conversation, label=label)
        add_audience_rule(
            actor=self.owner,
            audience_set=audience,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.EXPLICIT_PROFILE,
            profile=profile,
        )
        return audience

    def test_action_notification_never_outlives_point_visibility(self):
        visible_audience = self._audience(label="Visible", profile=self.visible)
        expected_audience = self._audience(label="Expected", profile=self.hidden)

        with self.captureOnCommitCallbacks(execute=True):
            point = create_point(
                actor=self.owner,
                conversation=self.conversation,
                kind=ConversationPointKind.QUESTION,
                response_mode=ConversationPointResponseMode.FREE_TEXT,
                title="Point privé",
                visibility_audience=visible_audience,
                response_audience=visible_audience,
                expected_action_audience=expected_audience,
            )

        self.assertFalse(point_visible_to(self.hidden, point))
        self.assertFalse(
            Notification.objects.filter(
                recipient=self.hidden,
                metadata__conversation_id=str(self.conversation.pk),
            ).exists()
        )


class DirectConversationCanonicalPairTests(TestCase):
    def test_direct_pair_is_canonical_regardless_of_initiator_order(self):
        profile_a = User.objects.create_user(
            username="j7-direct-a",
            email="j7-direct-a@example.test",
            password="StrongPass2026!",
        )
        profile_b = User.objects.create_user(
            username="j7-direct-b",
            email="j7-direct-b@example.test",
            password="StrongPass2026!",
        )
        ProfileContactPolicy.objects.create(profile=profile_a, mode=ContactPolicyMode.DIRECT)
        ProfileContactPolicy.objects.create(profile=profile_b, mode=ContactPolicyMode.DIRECT)

        first = ensure_direct_conversation(actor=profile_a, target=profile_b)
        second = ensure_direct_conversation(actor=profile_b, target=profile_a)

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(
            ConversationContext.objects.filter(
                kind=ConversationContextKind.DIRECT,
                purpose_key="coordination",
            ).count(),
            1,
        )
        context = first.context
        self.assertEqual(
            [str(context.direct_profile_a_id), str(context.direct_profile_b_id)],
            sorted([str(profile_a.pk), str(profile_b.pk)]),
        )
