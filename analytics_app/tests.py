from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization, OrganizationMembership, OrganizationRole
from payments.models import Payment, PaymentStatus, Refund, RefundStatus
from scanner.models import ScanLog, ScanResult
from tickets.models import (
    Ticket,
    TicketOrder,
    TicketOrderStatus,
    TicketStatus,
    TicketTransfer,
    TicketType,
    TicketWaitlistEntry,
    TransferStatus,
    WaitlistStatus,
)

from .services import build_event_analytics, build_portfolio_analytics


User = get_user_model()


class AnalyticsEventIntelligenceTests(TestCase):
    def setUp(self):
        now = timezone.now()
        self.owner = User.objects.create_user(
            username="analytics-owner",
            email="owner@analytics.test",
            password="Strong-password-2026!",
        )
        self.finance = User.objects.create_user(
            username="analytics-finance",
            email="finance@analytics.test",
            password="Strong-password-2026!",
        )
        self.marketing = User.objects.create_user(
            username="analytics-marketing",
            email="marketing@analytics.test",
            password="Strong-password-2026!",
        )
        self.scanner_manager = User.objects.create_user(
            username="analytics-scanner",
            email="scanner@analytics.test",
            password="Strong-password-2026!",
        )
        self.participant = User.objects.create_user(
            username="analytics-participant",
            email="participant@analytics.test",
            password="Strong-password-2026!",
        )
        self.outsider = User.objects.create_user(
            username="analytics-outsider",
            email="outsider@analytics.test",
            password="Strong-password-2026!",
        )

        self.organization = Organization.objects.create(
            name="Analytics Events",
            created_by=self.owner,
        )
        for user, role in [
            (self.owner, OrganizationRole.OWNER),
            (self.finance, OrganizationRole.FINANCE),
            (self.marketing, OrganizationRole.MARKETING),
            (self.scanner_manager, OrganizationRole.SCANNER_MANAGER),
        ]:
            OrganizationMembership.objects.create(
                organization=self.organization,
                user=user,
                role=role,
            )

        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Makolo Intelligence Summit",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=now + timedelta(days=10),
            end_at=now + timedelta(days=10, hours=4),
            capacity=20,
            published_at=now - timedelta(days=14),
        )
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Standard",
            price=Decimal("50.00"),
            currency="USD",
            quantity_total=20,
        )
        self.order = TicketOrder.objects.create(
            event=self.event,
            buyer=self.participant,
            customer_name="Participant Analytics",
            customer_email=self.participant.email,
            status=TicketOrderStatus.CONFIRMED,
            total_amount=Decimal("100.00"),
            currency="USD",
            confirmed_at=now - timedelta(days=1),
        )
        self.ticket_one = Ticket.objects.create(
            event=self.event,
            ticket_type=self.ticket_type,
            order=self.order,
            owner=self.participant,
            holder_name="Participant Analytics",
            holder_email=self.participant.email,
            status=TicketStatus.USED,
            used_at=now - timedelta(hours=1),
            issued_at=now - timedelta(days=1),
        )
        self.ticket_two = Ticket.objects.create(
            event=self.event,
            ticket_type=self.ticket_type,
            order=self.order,
            owner=self.participant,
            holder_name="Participant Analytics",
            holder_email=self.participant.email,
            status=TicketStatus.VALID,
            issued_at=now - timedelta(days=1),
        )
        self.payment = Payment.objects.create(
            order=self.order,
            initiated_by=self.participant,
            provider="sandbox",
            method="card",
            status=PaymentStatus.SUCCEEDED,
            amount=Decimal("100.00"),
            currency="USD",
            payer_name="Participant Analytics",
            payer_email=self.participant.email,
            succeeded_at=now - timedelta(days=1),
        )
        Refund.objects.create(
            payment=self.payment,
            requested_by=self.finance,
            status=RefundStatus.SUCCEEDED,
            amount=Decimal("20.00"),
            currency="USD",
            reason="Remboursement analytique partiel",
            processed_at=now,
        )
        self.cdf_order = TicketOrder.objects.create(
            event=self.event,
            buyer=self.participant,
            customer_name="Participant Analytics",
            customer_email=self.participant.email,
            status=TicketOrderStatus.CONFIRMED,
            total_amount=Decimal("20000.00"),
            currency="CDF",
            confirmed_at=now,
        )
        Payment.objects.create(
            order=self.cdf_order,
            initiated_by=self.participant,
            provider="sandbox",
            method="mobile_money",
            status=PaymentStatus.SUCCEEDED,
            amount=Decimal("20000.00"),
            currency="CDF",
            payer_name="Participant Analytics",
            payer_email=self.participant.email,
            succeeded_at=now,
        )
        ScanLog.objects.create(
            event=self.event,
            ticket=self.ticket_one,
            scanner=self.scanner_manager,
            result=ScanResult.ACCEPTED,
            message="Accès autorisé",
        )
        TicketWaitlistEntry.objects.create(
            ticket_type=self.ticket_type,
            user=self.outsider,
            requested_quantity=1,
            status=WaitlistStatus.WAITING,
        )
        TicketWaitlistEntry.objects.create(
            ticket_type=self.ticket_type,
            user=self.finance,
            requested_quantity=1,
            status=WaitlistStatus.CONVERTED,
            converted_at=now,
        )
        TicketTransfer.objects.create(
            ticket=self.ticket_two,
            sender=self.participant,
            recipient=self.finance,
            recipient_email=self.finance.email,
            status=TransferStatus.ACCEPTED,
            expires_at=now + timedelta(hours=12),
            accepted_at=now,
        )

    def test_owner_event_metrics_cover_sales_access_and_waitlist(self):
        analytics = build_event_analytics(self.event, self.owner, days=30)
        metrics = analytics["metrics"]

        self.assertEqual(metrics["active_tickets"], 2)
        self.assertEqual(metrics["used_tickets"], 1)
        self.assertEqual(metrics["attendance_percent"], 50.0)
        self.assertEqual(metrics["capacity_percent"], 10.0)
        self.assertEqual(metrics["confirmed_orders"], 2)
        self.assertEqual(metrics["payment_attempts"], 2)
        self.assertEqual(metrics["payment_conversion_percent"], 100.0)
        self.assertEqual(metrics["waitlist_waiting"], 1)
        self.assertEqual(metrics["waitlist_converted"], 1)
        self.assertEqual(metrics["transfers_accepted"], 1)
        self.assertTrue(any(item["title"] == "Demande non servie" for item in metrics["insights"]))

    def test_financial_totals_are_separated_by_currency(self):
        analytics = build_event_analytics(self.event, self.finance)
        totals = {row["currency"]: row for row in analytics["metrics"]["money_totals"]}

        self.assertTrue(analytics["metrics"]["financial_visible"])
        self.assertEqual(totals["USD"]["gross"], Decimal("100.00"))
        self.assertEqual(totals["USD"]["refunds"], Decimal("20.00"))
        self.assertEqual(totals["USD"]["net"], Decimal("80.00"))
        self.assertEqual(totals["CDF"]["net"], Decimal("20000.00"))

    def test_marketing_can_view_aggregates_but_not_financials(self):
        analytics = build_event_analytics(self.event, self.marketing)

        self.assertEqual(analytics["metrics"]["active_tickets"], 2)
        self.assertFalse(analytics["metrics"]["financial_visible"])
        self.assertEqual(analytics["metrics"]["money_totals"], [])

    def test_scanner_manager_can_view_operational_analytics_without_finance(self):
        self.client.force_login(self.scanner_manager)
        response = self.client.get(reverse("analytics:event-detail", args=[self.event.slug]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Flux d’entrée")
        self.assertContains(response, "métriques financières sont masquées")
        self.assertNotContains(response, "80.00 USD")

    def test_outsider_cannot_open_event_analytics(self):
        self.client.force_login(self.outsider)

        web_response = self.client.get(reverse("analytics:event-detail", args=[self.event.slug]))
        api_response = self.client.get(reverse("analytics_api:event-detail", args=[self.event.slug]))

        self.assertEqual(web_response.status_code, 404)
        self.assertEqual(api_response.status_code, 404)

    def test_participant_dashboard_has_no_organizer_event_data(self):
        self.client.force_login(self.participant)
        response = self.client.get(reverse("analytics:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["analytics"]["events_count"], 0)
        self.assertNotContains(response, self.event.title)

    def test_finance_portfolio_contains_money_but_no_pii(self):
        self.client.force_login(self.finance)
        response = self.client.get(reverse("analytics_api:overview"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["events_count"], 1)
        self.assertTrue(response.data["money_totals"])
        payload = response.content.decode()
        self.assertNotIn(self.participant.email, payload)
        self.assertNotIn("Participant Analytics", payload)

    def test_event_api_bounds_series_period_and_never_exposes_pii(self):
        self.client.force_login(self.marketing)
        response = self.client.get(
            reverse("analytics_api:event-detail", args=[self.event.slug]),
            {"days": 999},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["sales_series"]), 90)
        self.assertFalse(response.data["metrics"]["financial_visible"])
        payload = response.content.decode()
        self.assertNotIn(self.participant.email, payload)
        self.assertNotIn(self.payment.reference, payload)

    def test_dashboard_requires_authentication(self):
        response = self.client.get(reverse("analytics:dashboard"))

        self.assertEqual(response.status_code, 302)

    def test_ticket_type_breakdown_contains_operational_counts(self):
        analytics = build_event_analytics(self.event, self.owner)
        row = analytics["ticket_types"][0]

        self.assertEqual(row["name"], "Standard")
        self.assertEqual(row["active_count"], 2)
        self.assertEqual(row["used_count"], 1)
        self.assertEqual(row["waiting_count"], 1)

    def test_portfolio_is_scoped_to_authorized_events(self):
        other_org = Organization.objects.create(name="Other Analytics Org", created_by=self.outsider)
        other_event = Event.objects.create(
            organizer=self.outsider,
            organization=other_org,
            title="Private Portfolio Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=timezone.now() + timedelta(days=5),
            end_at=timezone.now() + timedelta(days=5, hours=2),
        )

        analytics = build_portfolio_analytics(self.marketing)
        titles = {row["event"].title for row in analytics["event_cards"]}

        self.assertIn(self.event.title, titles)
        self.assertNotIn(other_event.title, titles)
