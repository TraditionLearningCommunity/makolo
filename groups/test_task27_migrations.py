from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class Task27GroupMigrationTests(TransactionTestCase):
    migrate_from = [("groups", "0004_align_invitation_identity_constraint")]
    migrate_to = [("groups", "0005_community_layer")]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_legacy_visibility_is_backfilled_without_publication(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        User = old_apps.get_model("accounts", "User")
        Organization = old_apps.get_model("organizations", "Organization")
        Group = old_apps.get_model("groups", "Group")

        owner = User.objects.create(
            username="t27-migration-owner",
            email="t27-migration-owner@example.test",
            password="!",
        )
        private_group = Group.objects.create(
            name="T27 Legacy Private",
            slug="t27-legacy-private",
            owner_profile_id=owner.pk,
            created_by_id=owner.pk,
            visibility="private",
        )
        space = Organization.objects.create(
            name="T27 Legacy Space",
            slug="t27-legacy-space",
            created_by_id=owner.pk,
        )
        space_group = Group.objects.create(
            name="T27 Legacy Space Group",
            slug="t27-legacy-space-group",
            space_id=space.pk,
            created_by_id=owner.pk,
            visibility="space",
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        MigratedGroup = apps.get_model("groups", "Group")

        private_group = MigratedGroup.objects.get(pk=private_group.pk)
        space_group = MigratedGroup.objects.get(pk=space_group.pk)
        self.assertEqual(private_group.discoverability, "hidden")
        self.assertEqual(space_group.discoverability, "space_only")
        self.assertEqual(private_group.membership_policy, "invite_only")
        self.assertEqual(space_group.membership_policy, "invite_only")
        self.assertNotEqual(private_group.discoverability, "listed")
        self.assertNotEqual(space_group.discoverability, "listed")
