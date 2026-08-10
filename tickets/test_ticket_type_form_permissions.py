from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization, OrganizationMembership, OrganizationRole
from tickets.forms import TicketTypeForm


User = get_user_model()


class TicketTypeFormPermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="ticket-form-owner",
            email="ticket-form-owner@example.com",
            password="Strong-ticket-form-owner-2026!",
        )
        self.event_manager = User.objects.create_user(
            username="ticket-form-manager",
            email="ticket-form-manager@example.com",
            password="Strong-ticket-form-manager-2026!",
        )
        self.finance = User.objects.create_user(
            username="ticket-form-finance",
            email="ticket-form-finance@example.com",
            password="Strong-ticket-form-finance-2026!",
        )
        self.organization = Organization.objects.create(
            name="Ticket Form Organization",
            created_by=self.owner,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.owner,
            role=OrganizationRole.OWNER,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.event_manager,
            role=OrganizationRole.EVENT_MANAGER,
            is_active=True,
        )
        OrganizationMembership.objects.create(
            organization=self.organization,
            user=self.finance,
            role=OrganizationRole.FINANCE,
            is_active=True,
        )
        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Organization-managed ticket event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=3),
        )

    def test_event_manager_can_select_organization_event_owned_by_another_user(self):
        form = TicketTypeForm(user=self.event_manager)
        self.assertIn(self.event, form.fields["event"].queryset)

    def test_finance_only_member_cannot_select_event_for_ticket_configuration(self):
        form = TicketTypeForm(user=self.finance)
        self.assertNotIn(self.event, form.fields["event"].queryset)
