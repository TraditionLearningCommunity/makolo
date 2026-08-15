from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from access.models import CredentialStatus
from access.services import issue_access, render_access_credential, validate_access_credential
from activities.models import Activity, Occurrence
from capacity.models import CapacityPool, CapacityReservation, CapacityReservationStatus
from commerce.models import CommerceOrder, CommerceOrderStatus, PaymentMode
from core.models import DomainEventOutbox
from domain_events.contracts import DomainEventType
from events.models import Event, EventStatus, EventVisibility
from journeys.models import WorkflowKind
from journeys.services import confirm_journey, create_journey, submit_journey
from organizations.models import Organization
from payments.models import Payment, PaymentProvider, PaymentStatus, Refund, RefundStatus
from tickets.models import TicketType
from tickets.services import create_order as create_ticket_order

from .canonical import activity_summary, capacity_summary, occurrence_summary
from .domain_event_consumer import consume_analytics_event
from .models import AnalyticsFact


User = get_user_model()


class CanonicalAnalyticsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("analytics-core", "analytics-core@example.com", "Analytics-2026!")
        self.space = Organization.objects.create(name="Analytics canonical space", created_by=self.user)
        self.activity = Activity.objects.create(space=self.space, created_by=self.user, title="Registration activity")
        now = timezone.now()
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(hours=2),
        )

    def _confirmed_registration(self):
        journey = create_journey(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.REGISTRATION,
        )
        journey = submit_journey(journey=journey, actor=self.user)
        return confirm_journey(journey=journey, actor=self.user)

    def test_non_event_registration_and_access_are_measured_without_revenue(self):
        journey = self._confirmed_registration()
        for index in range(10):
            access = issue_access(
                beneficiary=self.user,
                activity=self.activity,
                occurrence=self.occurrence,
                journey=journey,
                source_key=f"registration:{index}",
            )
            if index < 7:
                token = render_access_credential(access.credentials.get(status=CredentialStatus.ACTIVE))
                validate_access_credential(
                    token,
                    expected_activity=self.activity,
                    expected_occurrence=self.occurrence,
                )

        summary = activity_summary(self.activity)
        self.assertEqual(summary["journey"]["confirmed"], 1)
        self.assertEqual(summary["journey"]["workflows"][WorkflowKind.REGISTRATION], 1)
        self.assertEqual(summary["access"]["issued"], 10)
        self.assertEqual(summary["access"]["used"], 7)
        self.assertEqual(summary["access"]["usage_rate"], 70.0)
        self.assertEqual(summary["commerce"]["orders_total"], 0)
        self.assertEqual(summary["payment"]["attempts"], 0)
        self.assertEqual(summary["payment"]["collected"], [])
        self.assertIsNone(getattr(self.activity, "event_vertical", None))

    def test_on_site_value_is_not_counted_as_collected_payment_and_currencies_stay_separate(self):
        journey = self._confirmed_registration()
        CommerceOrder.objects.create(
            journey=journey,
            buyer=self.user,
            payee_space=self.space,
            status=CommerceOrderStatus.CONFIRMED,
            currency="USD",
            payment_mode=PaymentMode.ON_SITE,
            subtotal=Decimal("20.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("20.00"),
        )
        CommerceOrder.objects.create(
            journey=journey,
            buyer=self.user,
            payee_space=self.space,
            status=CommerceOrderStatus.CONFIRMED,
            currency="CDF",
            payment_mode=PaymentMode.LATER,
            subtotal=Decimal("50000.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("50000.00"),
        )

        summary = activity_summary(self.activity)
        commercial = {row["currency"]: row["total"] for row in summary["commerce"]["commercial_value"]}
        self.assertEqual(commercial, {"CDF": Decimal("50000.00"), "USD": Decimal("20.00")})
        self.assertEqual(summary["payment"]["collected"], [])

    def test_success_and_refund_use_payment_truth_and_keep_commerce_history(self):
        journey = self._confirmed_registration()
        order = CommerceOrder.objects.create(
            journey=journey,
            buyer=self.user,
            payee_space=self.space,
            status=CommerceOrderStatus.CONFIRMED,
            currency="USD",
            payment_mode=PaymentMode.UPFRONT,
            subtotal=Decimal("30.00"),
            discount_total=Decimal("0.00"),
            total=Decimal("30.00"),
        )
        payment = Payment.objects.create(
            commerce_order=order,
            initiated_by=self.user,
            provider=PaymentProvider.SANDBOX,
            status=PaymentStatus.REFUNDED,
            amount=Decimal("30.00"),
            currency="USD",
        )
        Refund.objects.create(
            payment=payment,
            requested_by=self.user,
            status=RefundStatus.SUCCEEDED,
            amount=Decimal("10.00"),
            currency="USD",
        )

        summary = activity_summary(self.activity)
        paid = summary["payment"]["collected"][0]
        self.assertEqual(paid["gross"], Decimal("30.00"))
        self.assertEqual(paid["refunds"], Decimal("10.00"))
        self.assertEqual(paid["net"], Decimal("20.00"))
        self.assertEqual(summary["commerce"]["commercial_value"][0]["total"], Decimal("30.00"))

    def test_capacity_and_occurrence_metrics_use_canonical_pools(self):
        journey = self._confirmed_registration()
        pool = CapacityPool.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            label="Places",
            total_quantity=10,
        )
        CapacityReservation.objects.create(
            pool=pool,
            journey=journey,
            quantity=2,
            status=CapacityReservationStatus.HELD,
            expires_at=timezone.now() + timedelta(hours=1),
        )
        CapacityReservation.objects.create(
            pool=pool,
            journey=journey,
            quantity=3,
            status=CapacityReservationStatus.COMMITTED,
            committed_at=timezone.now(),
        )

        capacity = capacity_summary(self.activity, self.occurrence)
        self.assertEqual(capacity["total"], 10)
        self.assertEqual(capacity["held"], 2)
        self.assertEqual(capacity["committed"], 3)
        self.assertEqual(capacity["available"], 5)
        self.assertEqual(occurrence_summary(self.occurrence)["capacity"]["available"], 5)

    def test_analytics_domain_event_projection_is_idempotent(self):
        event = DomainEventOutbox.objects.create(
            event_type=DomainEventType.ACCESS_USED,
            source_type="access_use",
            source_id="test-use",
            space_id=self.space.pk,
            activity_id=self.activity.pk,
            idempotency_key="analytics-test:access-used",
            occurred_at=timezone.now(),
            payload={
                "beneficiary_id": str(self.user.pk),
                "occurrence_id": str(self.occurrence.pk),
            },
        )
        consume_analytics_event(event)
        consume_analytics_event(event)
        self.assertEqual(
            AnalyticsFact.objects.filter(domain_event=event, fact_type=DomainEventType.ACCESS_USED).count(),
            1,
        )

    def test_event_bridge_counts_canonical_order_and_access_once(self):
        start = timezone.now() + timedelta(days=1)
        event = Event.objects.create(
            organizer=self.user,
            organization=self.space,
            title="Analytics Event bridge",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=3),
        )
        ticket_type = TicketType.objects.create(
            event=event,
            name="Pass",
            price=Decimal("0.00"),
            currency="USD",
            quantity_total=10,
        )
        ticket_order = create_ticket_order(
            buyer=self.user,
            event=event,
            customer_name=self.user.full_name or self.user.username,
            customer_email=self.user.email,
            selections=[(ticket_type, 2)],
        )
        event.refresh_from_db()
        summary = activity_summary(event.activity)

        self.assertIsNotNone(ticket_order.commerce_order_id)
        self.assertEqual(summary["commerce"]["orders_total"], 1)
        self.assertEqual(summary["access"]["issued"], 2)
