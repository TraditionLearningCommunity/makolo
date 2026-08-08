from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility
from events.permissions import (
    user_can_manage_event,
    user_can_manage_event_access,
    user_can_manage_event_finance,
)
from payments.models import PaymentProvider, PaymentStatus
from payments.services import complete_manual_payment, initiate_payment, refund_payment
from tickets.models import TicketOrderStatus, TicketType
from tickets.services import create_order

from .models import OrganizationRole
from .services import add_or_update_member, create_organization


User = get_user_model()


class OrganizationPermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="org-owner",
            email="owner@makolo.test",
            password="StrongPass2026!",
        )
        self.event_manager = User.objects.create_user(
            username="event-manager",
            email="events@makolo.test",
            password="StrongPass2026!",
        )
        self.finance = User.objects.create_user(
            username="finance",
            email="finance@makolo.test",
            password="StrongPass2026!",
        )
        self.access = User.objects.create_user(
            username="access",
            email="access@makolo.test",
            password="StrongPass2026!",
        )
        self.buyer = User.objects.create_user(
            username="org-buyer",
            email="buyer@makolo.test",
            password="StrongPass2026!",
        )
        self.outsider = User.objects.create_user(
            username="outsider",
            email="outsider@makolo.test",
            password="StrongPass2026!",
        )
        self.organization = create_organization(
            creator=self.owner,
            name="Makolo Community Events",
        )
        add_or_update_member(
            organization=self.organization,
            actor=self.owner,
            user=self.event_manager,
            role=OrganizationRole.EVENT_MANAGER,
        )
        add_or_update_member(
            organization=self.organization,
            actor=self.owner,
            user=self.finance,
            role=OrganizationRole.FINANCE,
        )
        add_or_update_member(
            organization=self.organization,
            actor=self.owner,
            user=self.access,
            role=OrganizationRole.SCANNER_MANAGER,
        )
        start = timezone.now() + timedelta(days=5)
        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Community Day",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=4),
            capacity=100,
            published_at=timezone.now(),
        )

    def test_creator_becomes_owner(self):
        membership = self.organization.memberships.get(user=self.owner)
        self.assertEqual(membership.role, OrganizationRole.OWNER)
        self.assertTrue(membership.is_active)

    def test_event_manager_can_manage_event_but_not_finance(self):
        self.assertTrue(user_can_manage_event(self.event_manager, self.event))
        self.assertFalse(user_can_manage_event_finance(self.event_manager, self.event))

    def test_finance_has_finance_scope_without_event_edit_scope(self):
        self.assertFalse(user_can_manage_event(self.finance, self.event))
        self.assertTrue(user_can_manage_event_finance(self.finance, self.event))

    def test_access_manager_controls_scanner_without_event_edit_scope(self):
        self.assertFalse(user_can_manage_event(self.access, self.event))
        self.assertTrue(user_can_manage_event_access(self.access, self.event))

    def test_organization_workspace_is_available_to_member(self):
        self.client.force_login(self.event_manager)
        response = self.client.get(f"/organizations/{self.organization.slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Makolo Community Events")

    def test_non_member_cannot_open_private_team_workspace(self):
        self.client.force_login(self.outsider)
        response = self.client.get(f"/organizations/{self.organization.slug}/")
        self.assertEqual(response.status_code, 403)

    def test_public_profile_is_visible_without_team_data(self):
        response = self.client.get(f"/o/{self.organization.slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Makolo Community Events")
        self.assertContains(response, "Community Day")
        self.assertNotContains(response, self.finance.email)
        self.assertNotContains(response, "Finance")

    def test_finance_role_can_confirm_manual_payment_and_refund(self):
        ticket_type = TicketType.objects.create(
            event=self.event,
            name="Finance Pass",
            price=Decimal("25.00"),
            currency="USD",
            quantity_total=10,
        )
        order = create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name="Buyer",
            customer_email=self.buyer.email,
            selections=[(ticket_type, 1)],
        )
        payment = initiate_payment(
            order=order,
            actor=self.finance,
            provider=PaymentProvider.MANUAL,
            method="cash",
        )
        complete_manual_payment(
            payment=payment,
            actor=self.finance,
            provider_reference="ORG-CASH-001",
        )
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(order.status, TicketOrderStatus.CONFIRMED)

        refund_payment(
            payment=payment,
            actor=self.finance,
            reason="Test finance organization",
        )
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.REFUNDED)
        self.assertEqual(order.status, TicketOrderStatus.CANCELLED)
