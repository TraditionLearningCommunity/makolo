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


class PopulatedBetaUpgradeMigrationTests(TransactionTestCase):
    """Guard the populated beta upgrade path through all current migrations.

    Fresh CI databases do not contain legacy TicketOrder/Payment/Promotion rows
    when the canonical backfills execute. This fixture deliberately starts from
    the beta checkpoint that existed on PythonAnywhere after tickets.0007 and
    combines legacy-only rows with already-linked canonical projections.
    """

    migrate_from = [
        ("events", "0007_cutover_event_to_activity"),
        ("tickets", "0007_commerce_capacity_bridges"),
        ("payments", "0001_initial"),
        ("promotions", "0001_initial"),
        ("scanner", "0003_activity_occurrence_assignments"),
    ]

    def tearDown(self):
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        super().tearDown()

    def test_populated_beta_state_reaches_current_leaf_nodes(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.migrate_from)
        old_apps = executor.loader.project_state(self.migrate_from).apps

        User = old_apps.get_model("accounts", "User")
        Organization = old_apps.get_model("organizations", "Organization")
        Activity = old_apps.get_model("activities", "Activity")
        Occurrence = old_apps.get_model("activities", "Occurrence")
        Event = old_apps.get_model("events", "Event")
        Journey = old_apps.get_model("journeys", "Journey")
        CapacityPool = old_apps.get_model("capacity", "CapacityPool")
        CapacityReservation = old_apps.get_model("capacity", "CapacityReservation")
        Offer = old_apps.get_model("commerce", "Offer")
        CommerceOrder = old_apps.get_model("commerce", "CommerceOrder")
        CommerceOrderItem = old_apps.get_model("commerce", "CommerceOrderItem")
        TicketType = old_apps.get_model("tickets", "TicketType")
        TicketOrder = old_apps.get_model("tickets", "TicketOrder")
        TicketOrderItem = old_apps.get_model("tickets", "TicketOrderItem")
        Payment = old_apps.get_model("payments", "Payment")
        Promotion = old_apps.get_model("promotions", "Promotion")

        user = User.objects.create(
            username="beta-upgrade-buyer",
            email="beta-upgrade-buyer@example.test",
            password="!",
        )
        organization = Organization.objects.create(
            name="Beta upgrade space",
            slug="beta-upgrade-space",
            created_by_id=user.pk,
        )
        activity = Activity.objects.create(
            space_id=organization.pk,
            created_by_id=user.pk,
            title="Beta upgrade activity",
            slug="beta-upgrade-activity",
            status="published",
            visibility="public",
        )
        start_at = timezone.now() + timedelta(days=2)
        occurrence = Occurrence.objects.create(
            activity_id=activity.pk,
            start_at=start_at,
            end_at=start_at + timedelta(hours=4),
            timezone="Africa/Lubumbashi",
            status="scheduled",
        )
        event = Event.objects.create(
            activity_id=activity.pk,
            slug="beta-upgrade-event",
        )

        legacy_ticket_type = TicketType.objects.create(
            event_id=event.pk,
            name="Legacy only",
            slug="legacy-only",
            price="10.00",
            currency="USD",
            quantity_total=100,
            min_per_order=1,
            max_per_order=10,
            is_active=True,
        )

        existing_pool = CapacityPool.objects.create(
            activity_id=activity.pk,
            occurrence_id=occurrence.pk,
            label="Existing canonical pool",
            total_quantity=50,
            is_active=True,
            source_key="preexisting-beta-pool",
        )
        existing_offer = Offer.objects.create(
            activity_id=activity.pk,
            occurrence_id=occurrence.pk,
            capacity_pool_id=existing_pool.pk,
            name="Existing canonical offer",
            description="Already projected before the migration marker.",
            unit_price="20.00",
            currency="USD",
            payment_mode="upfront",
            min_quantity=1,
            max_quantity=5,
            status="active",
            source_key="preexisting-beta-offer",
        )
        projected_ticket_type = TicketType.objects.create(
            event_id=event.pk,
            offer_id=existing_offer.pk,
            capacity_pool_id=existing_pool.pk,
            name="Already canonical",
            slug="already-canonical",
            price="20.00",
            currency="USD",
            quantity_total=50,
            min_per_order=1,
            max_per_order=5,
            is_active=True,
        )

        journey_one = Journey.objects.create(
            initiated_by_id=user.pk,
            beneficiary_id=user.pk,
            activity_id=activity.pk,
            occurrence_id=occurrence.pk,
            workflow="purchase",
            status="confirmed",
        )
        journey_two = Journey.objects.create(
            initiated_by_id=user.pk,
            beneficiary_id=user.pk,
            activity_id=activity.pk,
            occurrence_id=occurrence.pk,
            workflow="purchase",
            status="confirmed",
        )

        order_one = TicketOrder.objects.create(
            reference="MIG-ORDER-LEGACY-001",
            event_id=event.pk,
            buyer_id=user.pk,
            journey_id=journey_one.pk,
            customer_name="Beta Buyer",
            customer_email=user.email,
            status="confirmed",
            total_amount="10.00",
            currency="USD",
            confirmed_at=timezone.now(),
        )
        item_one = TicketOrderItem.objects.create(
            order_id=order_one.pk,
            ticket_type_id=legacy_ticket_type.pk,
            quantity=1,
            unit_price="10.00",
        )

        existing_order = CommerceOrder.objects.create(
            reference="COM-PREEXIST-002",
            journey_id=journey_two.pk,
            buyer_id=user.pk,
            payee_space_id=organization.pk,
            status="confirmed",
            currency="USD",
            payment_mode="upfront",
            subtotal="20.00",
            discount_total="0.00",
            total="20.00",
            source_key="preexisting-beta-order",
            confirmed_at=timezone.now(),
        )
        order_two = TicketOrder.objects.create(
            reference="MIG-ORDER-PROJECTED-002",
            event_id=event.pk,
            buyer_id=user.pk,
            journey_id=journey_two.pk,
            commerce_order_id=existing_order.pk,
            customer_name="Beta Buyer",
            customer_email=user.email,
            status="confirmed",
            total_amount="20.00",
            currency="USD",
            confirmed_at=timezone.now(),
        )
        existing_reservation = CapacityReservation.objects.create(
            pool_id=existing_pool.pk,
            journey_id=journey_two.pk,
            quantity=1,
            status="committed",
            committed_at=timezone.now(),
            source_key="preexisting-beta-reservation",
        )
        existing_item = CommerceOrderItem.objects.create(
            order_id=existing_order.pk,
            offer_id=existing_offer.pk,
            beneficiary_id=user.pk,
            capacity_reservation_id=existing_reservation.pk,
            quantity=1,
            label_snapshot="Existing canonical offer",
            unit_price="20.00",
            line_subtotal="20.00",
            discount_total="0.00",
            line_total="20.00",
        )
        item_two = TicketOrderItem.objects.create(
            order_id=order_two.pk,
            ticket_type_id=projected_ticket_type.pk,
            commerce_item_id=existing_item.pk,
            quantity=1,
            unit_price="20.00",
        )

        payment = Payment.objects.create(
            reference="PAY-MIG-001",
            order_id=order_one.pk,
            initiated_by_id=user.pk,
            provider="manual",
            method="card",
            status="succeeded",
            amount="10.00",
            currency="USD",
            payer_name="Beta Buyer",
            payer_email=user.email,
            succeeded_at=timezone.now(),
        )

        promotion = Promotion.objects.create(
            organization_id=organization.pk,
            event_id=event.pk,
            name="Beta upgrade promotion",
            description="Historical promotion crossing the canonical upgrade.",
            discount_type="percent",
            discount_value="10.00",
            currency="USD",
            created_by_id=user.pk,
            is_active=True,
        )
        promotion.eligible_ticket_types.add(legacy_ticket_type, projected_ticket_type)

        executor = MigrationExecutor(connection)
        leaf_nodes = executor.loader.graph.leaf_nodes()
        executor.migrate(leaf_nodes)
        migrated_apps = executor.loader.project_state(leaf_nodes).apps

        MigratedTicketType = migrated_apps.get_model("tickets", "TicketType")
        MigratedOrder = migrated_apps.get_model("tickets", "TicketOrder")
        MigratedItem = migrated_apps.get_model("tickets", "TicketOrderItem")
        MigratedPayment = migrated_apps.get_model("payments", "Payment")
        MigratedCommerceOrder = migrated_apps.get_model("commerce", "CommerceOrder")
        PromotionTargeting = migrated_apps.get_model("promotions", "PromotionTargeting")
        PromotionOffer = migrated_apps.get_model("promotions", "PromotionOffer")

        migrated_order_one = MigratedOrder.objects.get(pk=order_one.pk)
        migrated_order_two = MigratedOrder.objects.get(pk=order_two.pk)
        self.assertIsNotNone(migrated_order_one.commerce_order_id)
        self.assertEqual(migrated_order_two.commerce_order_id, existing_order.pk)

        commerce_orders = list(
            MigratedCommerceOrder.objects.filter(
                pk__in=[migrated_order_one.commerce_order_id, migrated_order_two.commerce_order_id]
            ).order_by("pk")
        )
        self.assertEqual(len(commerce_orders), 2)
        self.assertTrue(all(order.reference for order in commerce_orders))
        self.assertEqual(len({order.reference for order in commerce_orders}), 2)
        self.assertEqual(
            MigratedCommerceOrder.objects.get(pk=existing_order.pk).reference,
            "COM-PREEXIST-002",
        )

        migrated_type_one = MigratedTicketType.objects.get(pk=legacy_ticket_type.pk)
        migrated_type_two = MigratedTicketType.objects.get(pk=projected_ticket_type.pk)
        self.assertIsNotNone(migrated_type_one.offer_id)
        self.assertIsNotNone(migrated_type_one.capacity_pool_id)
        self.assertEqual(migrated_type_two.offer_id, existing_offer.pk)
        self.assertEqual(migrated_type_two.capacity_pool_id, existing_pool.pk)

        migrated_item_one = MigratedItem.objects.get(pk=item_one.pk)
        migrated_item_two = MigratedItem.objects.get(pk=item_two.pk)
        self.assertIsNotNone(migrated_item_one.commerce_item_id)
        self.assertEqual(migrated_item_two.commerce_item_id, existing_item.pk)

        migrated_payment = MigratedPayment.objects.get(pk=payment.pk)
        self.assertEqual(
            migrated_payment.commerce_order_id,
            migrated_order_one.commerce_order_id,
        )

        targeting = PromotionTargeting.objects.get(promotion_id=promotion.pk)
        self.assertEqual(targeting.activity_id, activity.pk)
        self.assertEqual(
            PromotionOffer.objects.filter(promotion_id=promotion.pk).count(),
            2,
        )
