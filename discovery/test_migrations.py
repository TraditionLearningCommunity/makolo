from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class ActivityBookmarkMigrationTests(TransactionTestCase):
    migrate_from = [
        ("activities", "0003_activity_owner_profile"),
        ("events", "0007_cutover_event_to_activity"),
        ("discovery", "0001_initial"),
    ]
    migrate_to = [
        ("activities", "0003_activity_owner_profile"),
        ("events", "0007_cutover_event_to_activity"),
        ("discovery", "0002_activity_bookmark"),
    ]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_event_bookmark_is_backfilled_to_activity_with_timestamp(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        User = old_apps.get_model("accounts", "User")
        Activity = old_apps.get_model("activities", "Activity")
        Event = old_apps.get_model("events", "Event")
        EventBookmark = old_apps.get_model("discovery", "EventBookmark")

        user = User.objects.create(
            username="bookmark-migration-user",
            email="bookmark-migration@example.test",
            password="!",
        )
        activity = Activity.objects.create(
            owner_profile_id=user.pk,
            created_by_id=user.pk,
            title="Activity bookmark migration",
            slug="activity-bookmark-migration",
            status="published",
            visibility="public",
        )
        event = Event.objects.create(activity_id=activity.pk, slug="event-bookmark-migration")
        bookmark = EventBookmark.objects.create(user_id=user.pk, event_id=event.pk)
        expected_created_at = timezone.now() - timedelta(days=25)
        EventBookmark.objects.filter(pk=bookmark.pk).update(created_at=expected_created_at)

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        ActivityBookmark = apps.get_model("discovery", "ActivityBookmark")

        migrated = ActivityBookmark.objects.get(user_id=user.pk, activity_id=activity.pk)
        self.assertEqual(migrated.pk, bookmark.pk)
        self.assertEqual(migrated.created_at.replace(microsecond=0), expected_created_at.replace(microsecond=0))
        with self.assertRaises(LookupError):
            apps.get_model("discovery", "EventBookmark")
