from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from organizations.models import Organization

from .core_models import ConversationContextKind
from .presentation import conversation_rows_for_profile
from .services import activate_participation, ensure_context_conversation


User = get_user_model()


class ConversationListQueryBudgetTests(TestCase):
    def test_explicit_participation_list_query_count_is_bounded(self):
        owner = User.objects.create_user(username="m9c-conv-owner", email="m9c-conv-owner@example.test")
        manager = User.objects.create_user(username="m9c-conv-manager", email="m9c-conv-manager@example.test")
        profile = User.objects.create_user(username="m9c-conv-profile", email="m9c-conv-profile@example.test")
        space = Organization.objects.create(name="M9-C Conversation Space", created_by=owner)
        activity = Activity.objects.create(space=space, created_by=owner, title="M9-C Conversation Activity")
        grant_activity_role(
            profile=manager,
            activity=activity,
            role_code=SystemRoleCode.ACTIVITY_COMMUNICATION_MANAGER,
            granted_by=owner,
            source="m9c-query-budget",
        )
        conversation_count = 12
        for index in range(conversation_count):
            conversation = ensure_context_conversation(
                actor=manager,
                kind=ConversationContextKind.ACTIVITY,
                activity=activity,
                purpose_key=f"m9c-bounded-{index}",
                separation_reason="M9-C query growth fixture",
            )
            activate_participation(actor=manager, conversation=conversation, profile=profile)

        with CaptureQueriesContext(connection) as captured:
            rows = conversation_rows_for_profile(profile, only_attention=False, limit=50)

        self.assertEqual(len(rows), conversation_count)
        self.assertLessEqual(
            len(captured),
            8,
            f"conversation list must batch explicit participation/state/point reads; got {len(captured)} queries for {conversation_count} conversations",
        )
