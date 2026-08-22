from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class TicketJourneyAccessMigrationTests(TransactionTestCase):
    """Exercise the existing-database upgrade after the Event cutover."""

    migrate_from = [
        ("events", "0007_cutover_event_to_activity"),
        ("tickets", "0005_journey_access_bridges"),
    ]
    migrate_to = [
        ("events", "0007_cutover_event_to_activity"),
        ("tickets", "0006_backfill_journey_access"),
    ]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_existing_ticket_backfills_access_after_event_cutover(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        User = old_apps.get_model("accounts", "User")
        Activity = old_apps.get_model("activities", "Activity")
        Occurrence = old_apps.get_model("activities", "Occurrence")
        Event = old_apps.get_model("events", "Event")
        TicketType = old_apps.get_model("tickets", "TicketType")
        TicketOrder = old_apps.get_model("tickets", "TicketOrder")
        Ticket = old_apps.get_model("tickets", "Ticket")

        user = User.objects.create(
            username="ticket-migration-buyer",
            email="ticket-migration-buyer@example.test",
            password="!",
        )
        activity = Activity.objects.create(
            created_by_id=user.pk,
            title="Historical ticket activity",
            slug="historical-ticket-activity",
            status="published",
            visibility="public",
        )
        event = Event.objects.create(
            activity_id=activity.pk,
            slug="historical-ticket-event",
        )
        start_at = timezone.now() + timedelta(days=1)
        end_at = start_at + timedelta(hours=3)
        occurrence = Occurrence.objects.create(
            activity_id=activity.pk,
            start_at=start_at,
            end_at=end_at,
            timezone="Africa/Lubumbashi",
            status="scheduled",
        )
        ticket_type = TicketType.objects.create(
            event_id=event.pk,
            name="Historical ticket",
            slug="historical-ticket",
            price="10.00",
            currency="USD",
            quantity_total=20,
        )
        order = TicketOrder.objects.create(
            reference="MIG-TICKET-001",
            event_id=event.pk,
            buyer_id=user.pk,
            customer_name="Migration Buyer",
            customer_email=user.email,
            status="confirmed",
            total_amount="10.00",
            currency="USD",
        )
        ticket = Ticket.objects.create(
            event_id=event.pk,
            ticket_type_id=ticket_type.pk,
            order_id=order.pk,
            owner_id=user.pk,
            holder_name="Migration Buyer",
            holder_email=user.email,
            status="valid",
        )

        self.assertNotIn("start_at", {field.name for field in Event._meta.fields})
        self.assertNotIn("end_at", {field.name for field in Event._meta.fields})

        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_to)
        migrated_apps = executor.loader.project_state(self.migrate_to).apps
        MigratedTicket = migrated_apps.get_model("tickets", "Ticket")
        MigratedOrder = migrated_apps.get_model("tickets", "TicketOrder")
        Access = migrated_apps.get_model("access", "Access")
        Journey = migrated_apps.get_model("journeys", "Journey")

        migrated_ticket = MigratedTicket.objects.get(pk=ticket.pk)
        migrated_order = MigratedOrder.objects.get(pk=order.pk)
        self.assertIsNotNone(migrated_order.journey_id)
        self.assertIsNotNone(migrated_ticket.access_id)

        journey = Journey.objects.get(pk=migrated_order.journey_id)
        access = Access.objects.get(pk=migrated_ticket.access_id)
        self.assertEqual(journey.activity_id, activity.pk)
        self.assertEqual(journey.occurrence_id, occurrence.pk)
        self.assertEqual(access.activity_id, activity.pk)
        self.assertEqual(access.occurrence_id, occurrence.pk)
        self.assertEqual(access.journey_id, journey.pk)
        self.assertEqual(access.valid_until, end_at)
