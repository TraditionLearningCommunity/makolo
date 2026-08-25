from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization, OrganizationMembership, OrganizationRole
from payments.models import Payment, PaymentMethod, PaymentProvider
from payments.selectors import get_payment_events_visible_to, get_payments_visible_to
from scanner.selectors import get_scannable_events
from tickets.models import Ticket, TicketOrder, TicketOrderStatus, TicketType
from tickets.selectors import get_orders_visible_to, get_tickets_visible_to


User = get_user_model()


class OrganizationCapabilityBoundaryTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="boundary-owner",
            email="boundary-owner@example.com",
            password="Strong-boundary-password-2026!",
            is_organizer=True,
        )
        self.event_manager = User.objects.create_user(
            username="boundary-events",
            email="boundary-events@example.com",
            password="Strong-boundary-password-2026!",
        )
        self.finance = User.objects.create_user(
            username="boundary-finance",
            email="boundary-finance@example.com",
            password="Strong-boundary-password-2026!",
        )
        self.marketing = User.objects.create_user(
            username="boundary-marketing",
            email="boundary-marketing@example.com",
            password="Strong-boundary-password-2026!",
        )
        self.access_manager = User.objects.create_user(
            username="boundary-access",
            email="boundary-access@example.com",
            password="Strong-boundary-password-2026!",
        )
        self.buyer = User.objects.create_user(
            username="boundary-buyer",
            email="boundary-buyer@example.com",
            password="Strong-boundary-password-2026!",
        )

        self.organization = Organization.objects.create(
            name="Boundary Events",
            created_by=self.owner,
        )
        memberships = (
            (self.owner, OrganizationRole.OWNER),
            (self.event_manager, OrganizationRole.EVENT_MANAGER),
            (self.finance, OrganizationRole.FINANCE),
            (self.marketing, OrganizationRole.MARKETING),
            (self.access_manager, OrganizationRole.SCANNER_MANAGER),
        )
        for user, role in memberships:
            OrganizationMembership.objects.create(
                organization=self.organization,
                user=user,
                role=role,
            )

        now = timezone.now()
        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Boundary Live Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=now + timedelta(days=3),
            end_at=now + timedelta(days=3, hours=3),
            registration_start_at=now - timedelta(hours=1),
            registration_end_at=now + timedelta(days=3),
            capacity=100,
            published_at=now,
        )
        self.draft_event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Boundary Draft Event",
            status=EventStatus.DRAFT,
            visibility=EventVisibility.PRIVATE,
            start_at=now + timedelta(days=10),
            end_at=now + timedelta(days=10, hours=2),
            capacity=50,
        )
        self.ticket_type = TicketType.objects.create(
            event=self.event,
            name="Boundary Standard",
            price=Decimal("0.00"),
            quantity_total=100,
        )
        self.order = TicketOrder.objects.create(
            event=self.event,
            buyer=self.buyer,
            customer_name="Boundary Buyer",
            customer_email=self.buyer.email,
            status=TicketOrderStatus.CONFIRMED,
            total_amount=Decimal("0.00"),
            currency="USD",
            confirmed_at=now,
        )
        self.ticket = Ticket.objects.create(
            event=self.event,
            ticket_type=self.ticket_type,
            order=self.order,
            owner=self.buyer,
            holder_name="Boundary Buyer",
            holder_email=self.buyer.email,
        )
        self.paid_order = TicketOrder.objects.create(
            event=self.event,
            buyer=self.buyer,
            customer_name="Boundary Buyer",
            customer_email=self.buyer.email,
            total_amount=Decimal("20.00"),
            currency="USD",
            expires_at=now + timedelta(minutes=20),
        )
        self.payment = Payment.objects.create(
            order=self.paid_order,
            initiated_by=self.buyer,
            provider=PaymentProvider.SANDBOX,
            method=PaymentMethod.CARD,
            amount=Decimal("20.00"),
            currency="USD",
            payer_name="Boundary Buyer",
            payer_email=self.buyer.email,
        )

    def test_order_visibility_requires_buyer_event_or_finance_capability(self):
        self.assertTrue(get_orders_visible_to(self.event_manager).filter(pk=self.order.pk).exists())
        self.assertTrue(get_orders_visible_to(self.finance).filter(pk=self.order.pk).exists())
        self.assertFalse(get_orders_visible_to(self.marketing).filter(pk=self.order.pk).exists())
        self.assertFalse(get_orders_visible_to(self.access_manager).filter(pk=self.order.pk).exists())
        self.assertTrue(get_orders_visible_to(self.buyer).filter(pk=self.order.pk).exists())

    def test_ticket_holder_data_is_not_exposed_to_marketing_or_finance(self):
        self.assertTrue(get_tickets_visible_to(self.event_manager).filter(pk=self.ticket.pk).exists())
        self.assertTrue(get_tickets_visible_to(self.access_manager).filter(pk=self.ticket.pk).exists())
        self.assertFalse(get_tickets_visible_to(self.marketing).filter(pk=self.ticket.pk).exists())
        self.assertFalse(get_tickets_visible_to(self.finance).filter(pk=self.ticket.pk).exists())
        self.assertTrue(get_tickets_visible_to(self.buyer).filter(pk=self.ticket.pk).exists())

    def test_payment_visibility_is_finance_only_for_organization_team(self):
        self.assertTrue(get_payments_visible_to(self.finance).filter(pk=self.payment.pk).exists())
        self.assertFalse(get_payments_visible_to(self.event_manager).filter(pk=self.payment.pk).exists())
        self.assertFalse(get_payments_visible_to(self.marketing).filter(pk=self.payment.pk).exists())
        self.assertFalse(get_payments_visible_to(self.access_manager).filter(pk=self.payment.pk).exists())
        self.assertTrue(get_payments_visible_to(self.buyer).filter(pk=self.payment.pk).exists())
        self.assertFalse(get_payment_events_visible_to(self.event_manager).exists())

    def test_scanner_manager_gets_operational_event_without_finance_visibility(self):
        self.assertTrue(get_scannable_events(self.access_manager).filter(pk=self.event.pk).exists())
        self.assertFalse(get_scannable_events(self.marketing).filter(pk=self.event.pk).exists())
        self.assertFalse(get_payments_visible_to(self.access_manager).filter(pk=self.payment.pk).exists())

    def test_legacy_dashboard_redirects_professional_to_personal_context(self):
        self.client.force_login(self.event_manager)
        response = self.client.get(reverse("core:dashboard"))
        self.assertRedirects(
            response,
            reverse("core:participant-home"),
            fetch_redirect_response=False,
        )
