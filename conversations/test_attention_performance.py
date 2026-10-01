from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from activities.involvement_models import (
    ActivityInvolvement,
    ActivityInvolvementConfirmationBasis,
    ActivityInvolvementFunction,
    ActivityInvolvementFunctionKind,
)
from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from organizations.models import Organization

from .attention import attention_points_for_profile
from .audience_models import (
    ConversationAudienceRuleKind,
    ConversationAudienceRuleOperation,
)
from .audience_services import add_audience_rule, create_audience_set
from .core_models import ConversationContextKind
from .point_models import ConversationPointKind, ConversationPointResponseMode
from .point_services import create_point
from .services import ensure_context_conversation


User = get_user_model()


class ConversationAttentionPerformanceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="attention-perf-owner",
            email="attention-perf-owner@example.test",
            password="AttentionPerf2026!",
        )
        self.manager = User.objects.create_user(
            username="attention-perf-manager",
            email="attention-perf-manager@example.test",
            password="AttentionPerf2026!",
        )
        self.profile = User.objects.create_user(
            username="attention-perf-profile",
            email="attention-perf-profile@example.test",
            password="AttentionPerf2026!",
        )
        self.space = Organization.objects.create(
            name="Attention performance",
            created_by=self.owner,
        )
        self.activity = Activity.objects.create(
            space=self.space,
            created_by=self.owner,
            title="Attention performance activity",
        )
        grant_activity_role(
            profile=self.manager,
            activity=self.activity,
            role_code=SystemRoleCode.ACTIVITY_COMMUNICATION_MANAGER,
            granted_by=self.owner,
            source="attention-performance",
        )
        self.conversation = ensure_context_conversation(
            actor=self.manager,
            kind=ConversationContextKind.ACTIVITY,
            activity=self.activity,
        )
        involvement = ActivityInvolvement.objects.create(
            activity=self.activity,
            profile=self.profile,
            confirmation_basis=ActivityInvolvementConfirmationBasis.PROFILE_CONFIRMED,
            recorded_by=self.owner,
            confirmed_by=self.profile,
        )
        ActivityInvolvementFunction.objects.create(
            involvement=involvement,
            kind=ActivityInvolvementFunctionKind.SPEAKER,
        )
        self.speakers = create_audience_set(
            actor=self.manager,
            conversation=self.conversation,
            label="Attention performance speakers",
        )
        add_audience_rule(
            actor=self.manager,
            audience_set=self.speakers,
            operation=ConversationAudienceRuleOperation.INCLUDE,
            kind=ConversationAudienceRuleKind.ACTIVITY_INVOLVEMENT_FUNCTION,
            activity=self.activity,
            involvement_function_kind=ActivityInvolvementFunctionKind.SPEAKER,
        )

    def _create_attention_points(self, count):
        for index in range(count):
            create_point(
                actor=self.manager,
                conversation=self.conversation,
                kind=ConversationPointKind.QUESTION,
                response_mode=ConversationPointResponseMode.FREE_TEXT,
                title=f"Attention performance {index}",
                visibility_audience=self.speakers,
                response_audience=self.speakers,
                expected_action_audience=self.speakers,
            )

    def _query_count(self):
        with CaptureQueriesContext(connection) as queries:
            items = attention_points_for_profile(self.profile, limit=100)
        return len(queries), items

    def test_shared_conversation_and_audience_do_not_create_point_n_plus_one(self):
        self._create_attention_points(1)
        one_queries, one_items = self._query_count()
        self.assertEqual(len(one_items), 1)

        self._create_attention_points(19)
        many_queries, many_items = self._query_count()
        self.assertEqual(len(many_items), 20)
        self.assertLessEqual(many_queries, one_queries + 1)
