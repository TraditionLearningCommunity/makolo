from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from activities.models import Activity
from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role
from organizations.models import Organization

from .core_models import ConversationContextKind
from .point_models import ConversationPointKind, ConversationPointResponseMode
from .point_services import create_point
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

    def test_active_point_attention_reads_are_batched_for_the_viewer(self):
        owner = User.objects.create_user(username="m9c-points-owner", email="m9c-points-owner@example.test")
        manager = User.objects.create_user(username="m9c-points-manager", email="m9c-points-manager@example.test")
        profile = User.objects.create_user(username="m9c-points-viewer", email="m9c-points-viewer@example.test")
        space = Organization.objects.create(name="M9-C Point Query Space", created_by=owner)
        activity = Activity.objects.create(space=space, created_by=owner, title="M9-C Point Query Activity")
        grant_activity_role(
            profile=manager, activity=activity,
            role_code=SystemRoleCode.ACTIVITY_COMMUNICATION_MANAGER,
            granted_by=owner, source="m9c-points-query-budget",
        )
        for index in range(12):
            conversation = ensure_context_conversation(
                actor=manager, kind=ConversationContextKind.ACTIVITY,
                activity=activity, purpose_key=f"m9c-point-{index}",
                separation_reason="M9-C point query fixture",
            )
            activate_participation(actor=manager, conversation=conversation, profile=profile)
            create_point(
                actor=manager, conversation=conversation,
                kind=ConversationPointKind.QUESTION,
                response_mode=ConversationPointResponseMode.FREE_TEXT,
                title=f"Question {index}",
            )

        with CaptureQueriesContext(connection) as captured:
            rows = conversation_rows_for_profile(profile, limit=50)

        self.assertEqual(len(rows), 12)
        # No per-Point SELECT for response or viewer state: these must be
        # prefetched once across the bounded Conversation list.
        for table in ("conversations_conversationpointresponse", "conversations_conversationpointuserstate"):
            selects = [
                query["sql"] for query in captured
                if query["sql"].lstrip().upper().startswith("SELECT") and table in query["sql"].lower()
            ]
            self.assertLessEqual(
                len(selects), 2,
                f"viewer Point state/response reads should be batched for {table}: {len(selects)}",
            )
