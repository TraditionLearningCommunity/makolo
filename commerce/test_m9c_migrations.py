from decimal import Decimal

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class CommerceFinancialSnapshotMigrationTests(TransactionTestCase):
    migrate_from = [
        ("accounts", "0006_remove_legacy_account_truths"),
        ("activities", "0004_occurrence_temporal_schedule"),
        ("journeys", "0002_external_beneficiary"),
        ("commerce", "0002_payment_choices_personal_payee_beneficiary"),
    ]
    migrate_to = [
        ("accounts", "0006_remove_legacy_account_truths"),
        ("activities", "0004_occurrence_temporal_schedule"),
        ("journeys", "0002_external_beneficiary"),
        ("commerce", "0003_financial_quote_snapshot"),
    ]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_legacy_order_totals_become_financial_snapshot_without_inventing_provider_truth(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        User = old_apps.get_model("accounts", "User")
        Activity = old_apps.get_model("activities", "Activity")
        Journey = old_apps.get_model("journeys", "Journey")
        Offer = old_apps.get_model("commerce", "Offer")
        CommerceOrder = old_apps.get_model("commerce", "CommerceOrder")
        CommerceOrderItem = old_apps.get_model("commerce", "CommerceOrderItem")

        user = User.objects.create(username="m9c-commerce-legacy", email="m9c-commerce-legacy@example.test", password="!")
        activity = Activity.objects.create(created_by_id=user.pk, title="M9-C historical activity", slug="m9c-historical-activity")
        journey = Journey.objects.create(
            initiated_by_id=user.pk,
            beneficiary_id=user.pk,
            activity_id=activity.pk,
            workflow="purchase",
            status="confirmed",
        )
        offer = Offer.objects.create(
            activity_id=activity.pk,
            name="Historical offer",
            unit_price=Decimal("125.00"),
            currency="USD",
            payment_mode="upfront",
            status="active",
        )
        order = CommerceOrder.objects.create(
            reference="M9C-LEGACY-001",
            journey_id=journey.pk,
            buyer_id=user.pk,
            status="confirmed",
            currency="USD",
            payment_mode="upfront",
            subtotal=Decimal("250.00"),
            discount_total=Decimal("25.00"),
            total=Decimal("225.00"),
        )
        CommerceOrderItem.objects.create(
            order_id=order.pk,
            offer_id=offer.pk,
            beneficiary_id=user.pk,
            quantity=2,
            label_snapshot="Historical offer",
            unit_price=Decimal("125.00"),
            line_subtotal=Decimal("250.00"),
            discount_total=Decimal("25.00"),
            line_total=Decimal("225.00"),
        )

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        migrated_apps = executor.loader.project_state(self.migrate_to).apps
        MigratedOrder = migrated_apps.get_model("commerce", "CommerceOrder")
        MigratedItem = migrated_apps.get_model("commerce", "CommerceOrderItem")

        migrated_order = MigratedOrder.objects.get(pk=order.pk)
        migrated_item = MigratedItem.objects.get(order_id=order.pk)
        self.assertEqual(migrated_order.expected_payee_amount, Decimal("225.00"))
        self.assertEqual(migrated_order.financial_snapshot["legacy_total"], "225.00")
        self.assertEqual(migrated_order.financial_snapshot["legacy_currency"], "USD")
        self.assertEqual(migrated_order.financial_snapshot["legacy_payment_mode"], "upfront")
        self.assertEqual(migrated_order.financial_snapshot["source"], "commerce_v1_backfill")
        self.assertNotIn("provider", migrated_order.financial_snapshot)
        self.assertNotIn("destination", migrated_order.financial_snapshot)
        self.assertEqual(migrated_item.expected_payee_amount, Decimal("225.00"))
        self.assertEqual(migrated_item.financial_snapshot["legacy_line_total"], "225.00")
        self.assertEqual(migrated_item.financial_snapshot["legacy_currency"], "USD")
        self.assertEqual(migrated_item.financial_snapshot["source"], "commerce_v1_backfill")
