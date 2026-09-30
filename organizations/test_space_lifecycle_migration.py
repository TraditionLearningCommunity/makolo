from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class SpaceLifecycleMigrationTests(TransactionTestCase):
    migrate_from = [("organizations", "0005_organization_archetype")]
    migrate_to = [("organizations", "0006_organization_lifecycle")]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_legacy_suspended_only_backfills_lifecycle(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps
        User = old_apps.get_model("accounts", "User")
        Organization = old_apps.get_model("organizations", "Organization")
        owner = User.objects.create(
            username="space-lifecycle-migration-owner",
            email="space-lifecycle-migration-owner@test.local",
            password="!",
        )
        suspended = Organization.objects.create(
            name="Legacy Suspended",
            slug="legacy-suspended",
            created_by_id=owner.pk,
            verification_status="suspended",
        )
        ordinary = Organization.objects.create(
            name="Legacy Ordinary",
            slug="legacy-ordinary",
            created_by_id=owner.pk,
            verification_status="new",
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        apps = executor.loader.project_state(self.migrate_to).apps
        MigratedOrganization = apps.get_model("organizations", "Organization")
        suspended = MigratedOrganization.objects.get(pk=suspended.pk)
        ordinary = MigratedOrganization.objects.get(pk=ordinary.pk)
        self.assertEqual(suspended.lifecycle, "suspended")
        self.assertEqual(ordinary.lifecycle, "active")
        self.assertEqual(suspended.verification_status, "suspended")
        self.assertEqual(ordinary.verification_status, "new")
