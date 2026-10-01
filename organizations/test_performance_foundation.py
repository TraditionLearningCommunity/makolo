from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from authorization.constants import SystemRoleCode
from authorization.services import grant_activity_role, grant_space_role
from activities.models import Activity
from organizations.console_context import SpaceConsoleContext
from organizations.models import Organization


User = get_user_model()


class SpaceReadPathPerformanceTests(TestCase):
    def setUp(self):
        self.creator = User.objects.create_user(
            username="space-perf-creator",
            email="space-perf-creator@example.test",
            password="SpacePerf2026!",
        )
        self.owner = User.objects.create_user(
            username="space-perf-owner",
            email="space-perf-owner@example.test",
            password="SpacePerf2026!",
        )
        self.primary = Organization.objects.create(
            name="Space performance principal",
            created_by=self.creator,
        )
        grant_space_role(
            profile=self.owner,
            space=self.primary,
            role=SystemRoleCode.SPACE_OWNER,
        )

    def _build_count(self):
        with CaptureQueriesContext(connection) as queries:
            context = SpaceConsoleContext.build(self.owner, self.primary)
        self.assertIsNotNone(context)
        return len(queries), context

    def test_space_switcher_query_growth_is_bounded_across_authorized_spaces(self):
        one_queries, one_context = self._build_count()
        self.assertEqual(len(one_context.switcher_items), 1)

        for index in range(5):
            space = Organization.objects.create(
                name=f"Space performance {index}",
                created_by=self.creator,
            )
            grant_space_role(
                profile=self.owner,
                space=space,
                role=SystemRoleCode.SPACE_OWNER,
            )

        many_queries, many_context = self._build_count()
        self.assertEqual(len(many_context.switcher_items), 6)
        self.assertLessEqual(many_queries, one_queries + 1)

    def test_activity_scope_does_not_become_space_authority(self):
        limited_user = User.objects.create_user(
            username="space-perf-limited",
            email="space-perf-limited@example.test",
            password="SpacePerf2026!",
        )
        activity = Activity.objects.create(
            space=self.primary,
            created_by=self.creator,
            title="Activity scoped only",
        )
        grant_activity_role(
            profile=limited_user,
            activity=activity,
            role=SystemRoleCode.ACTIVITY_LOCAL_MANAGER,
        )

        context = SpaceConsoleContext.build(limited_user, self.primary)
        self.assertIsNotNone(context)
        self.assertTrue(context.limited_to_activities)
        self.assertEqual(context.activity_ids, frozenset({activity.pk}))
