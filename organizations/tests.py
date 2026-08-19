from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from authorization.constants import PermissionCode, SystemRoleCode
from authorization.models import Mandate, MandateStatus
from authorization.services import can, get_system_role, revoke_mandate
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

from .models import (
    OrganizationMembership,
    OrganizationRole,
    TeamMembership,
    TeamMembershipStatus,
)
from .services import add_or_update_member, create_organization, deactivate_member


User = get_user_model()


class OrganizationPermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="org-owner", email="owner@makolo.test", password="StrongPass2026!")
        self.event_manager = User.objects.create_user(username="event-manager", email="events@makolo.test", password="StrongPass2026!")
        self.finance = User.objects.create_user(username="finance", email="finance@makolo.test", password="StrongPass2026!")
        self.marketing = User.objects.create_user(username="marketing", email="marketing@makolo.test", password="StrongPass2026!")
        self.access = User.objects.create_user(username="access", email="access@makolo.test", password="StrongPass2026!")
        self.buyer = User.objects.create_user(username="org-buyer", email="buyer@makolo.test", password="StrongPass2026!")
        self.outsider = User.objects.create_user(username="outsider", email="outsider@makolo.test", password="StrongPass2026!")
        self.organization = create_organization(creator=self.owner, name="Makolo Community Events")
        add_or_update_member(organization=self.organization, actor=self.owner, user=self.event_manager, role=OrganizationRole.EVENT_MANAGER)
        add_or_update_member(organization=self.organization, actor=self.owner, user=self.finance, role=OrganizationRole.FINANCE)
        add_or_update_member(organization=self.organization, actor=self.owner, user=self.marketing, role=OrganizationRole.MARKETING)
        add_or_update_member(organization=self.organization, actor=self.owner, user=self.access, role=OrganizationRole.SCANNER_MANAGER)
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

    def test_creator_gets_default_team_membership_owner_mandate_and_legacy_projection(self):
        teams = list(self.organization.teams.all())
        self.assertEqual(len(teams), 1)
        self.assertTrue(teams[0].is_default)
        self.assertTrue(teams[0].is_active)
        team_membership = TeamMembership.objects.get(team=teams[0], user=self.owner)
        self.assertEqual(team_membership.status, TeamMembershipStatus.ACTIVE)
        mandate = Mandate.objects.get(profile=self.owner, space=self.organization, status=MandateStatus.ACTIVE)
        self.assertEqual(mandate.role.code, SystemRoleCode.SPACE_OWNER)
        self.assertTrue(can(self.owner, PermissionCode.SPACE_OWNERSHIP_MANAGE, self.organization))
        legacy = OrganizationMembership.objects.get(organization=self.organization, user=self.owner)
        self.assertEqual(legacy.role, OrganizationRole.OWNER)
        self.assertTrue(legacy.is_active)

    def test_event_manager_can_manage_event_but_not_finance(self):
        self.assertTrue(user_can_manage_event(self.event_manager, self.event))
        self.assertFalse(user_can_manage_event_finance(self.event_manager, self.event))

    def test_finance_has_finance_scope_without_event_edit_scope(self):
        self.assertFalse(user_can_manage_event(self.finance, self.event))
        self.assertTrue(user_can_manage_event_finance(self.finance, self.event))
        self.assertFalse(can(self.finance, PermissionCode.CRM_MANAGE, self.organization))

    def test_marketing_has_marketing_without_finance(self):
        self.assertTrue(can(self.marketing, PermissionCode.MARKETING_MANAGE, self.organization))
        self.assertTrue(can(self.marketing, PermissionCode.CRM_MANAGE, self.organization))
        self.assertFalse(can(self.marketing, PermissionCode.FINANCE_VIEW, self.organization))

    def test_access_manager_controls_scanner_without_event_edit_or_finance(self):
        self.assertFalse(user_can_manage_event(self.access, self.event))
        self.assertTrue(user_can_manage_event_access(self.access, self.event))
        self.assertFalse(can(self.access, PermissionCode.FINANCE_VIEW, self.organization))

    def test_member_update_keeps_team_mandate_and_legacy_projection_synchronized(self):
        membership = add_or_update_member(organization=self.organization, actor=self.owner, user=self.event_manager, role=SystemRoleCode.FINANCE)
        self.assertIsInstance(membership, TeamMembership)
        self.assertEqual(membership.status, TeamMembershipStatus.ACTIVE)
        active_roles = set(Mandate.objects.filter(profile=self.event_manager, space=self.organization, status=MandateStatus.ACTIVE).values_list("role__code", flat=True))
        self.assertEqual(active_roles, {SystemRoleCode.FINANCE})
        legacy = OrganizationMembership.objects.get(organization=self.organization, user=self.event_manager)
        self.assertEqual(legacy.role, OrganizationRole.FINANCE)

    def test_space_admin_cannot_grant_space_ownership(self):
        admin = User.objects.create_user(username="space-admin", email="space-admin@makolo.test", password="StrongPass2026!")
        target = User.objects.create_user(username="owner-target", email="owner-target@makolo.test", password="StrongPass2026!")
        add_or_update_member(organization=self.organization, actor=self.owner, user=admin, role=SystemRoleCode.SPACE_ADMIN)
        self.assertTrue(can(admin, PermissionCode.SPACE_TEAM_MANAGE, self.organization))
        self.assertFalse(can(admin, PermissionCode.SPACE_OWNERSHIP_MANAGE, self.organization))
        with self.assertRaises(PermissionDenied):
            add_or_update_member(organization=self.organization, actor=admin, user=target, role=SystemRoleCode.SPACE_OWNER)

    def test_last_owner_cannot_be_revoked_or_removed(self):
        mandate = Mandate.objects.get(profile=self.owner, space=self.organization, role__code=SystemRoleCode.SPACE_OWNER, status=MandateStatus.ACTIVE)
        with self.assertRaises(ValidationError):
            revoke_mandate(mandate=mandate, actor=self.owner)
        membership = TeamMembership.objects.get(team__organization=self.organization, user=self.owner)
        with self.assertRaises(ValidationError):
            deactivate_member(membership=membership, actor=self.owner)

    def test_owner_can_leave_after_second_owner_exists(self):
        second_owner = User.objects.create_user(username="second-owner", email="second-owner@makolo.test", password="StrongPass2026!")
        add_or_update_member(organization=self.organization, actor=self.owner, user=second_owner, role=SystemRoleCode.SPACE_OWNER)
        membership = TeamMembership.objects.get(team__organization=self.organization, user=self.owner)
        deactivate_member(membership=membership, actor=second_owner)
        membership.refresh_from_db()
        self.assertEqual(membership.status, TeamMembershipStatus.INACTIVE)
        self.assertFalse(Mandate.objects.filter(profile=self.owner, space=self.organization, status=MandateStatus.ACTIVE).exists())
        self.assertTrue(can(second_owner, PermissionCode.SPACE_OWNERSHIP_MANAGE, self.organization))

    def test_space_console_is_available_to_authorized_team_member(self):
        self.client.force_login(self.event_manager)
        response = self.client.get(f"/spaces/{self.organization.slug}/")
        self.assertEqual(response.status_code, 302)
        response = self.client.get(f"/spaces/{self.organization.slug}/overview/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Makolo Community Events")
        self.assertContains(response, "Agir au nom de")

    def test_non_member_cannot_open_space_console(self):
        self.client.force_login(self.outsider)
        response = self.client.get(f"/spaces/{self.organization.slug}/overview/")
        self.assertEqual(response.status_code, 403)

    def test_team_member_without_mandate_cannot_open_space_console(self):
        team = self.organization.teams.get(is_default=True)
        TeamMembership.objects.create(team=team, user=self.outsider, status=TeamMembershipStatus.ACTIVE, joined_at=timezone.now())
        self.client.force_login(self.outsider)
        response = self.client.get(f"/spaces/{self.organization.slug}/overview/")
        self.assertEqual(response.status_code, 403)

    def test_cannot_manage_team_of_another_space(self):
        other_owner = User.objects.create_user(username="other-owner", email="other-owner@makolo.test", password="StrongPass2026!")
        other = create_organization(creator=other_owner, name="Other Space")
        self.client.force_login(self.owner)
        response = self.client.get(f"/spaces/{other.slug}/team/add/")
        self.assertEqual(response.status_code, 403)

    def test_web_team_invitation_creates_team_membership_and_mandate(self):
        target = User.objects.create_user(username="invited-finance", email="invited-finance@makolo.test", password="StrongPass2026!")
        self.client.force_login(self.owner)
        response = self.client.post(
            f"/spaces/{self.organization.slug}/team/add/",
            {"email": target.email, "role": SystemRoleCode.FINANCE},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(TeamMembership.objects.filter(team__organization=self.organization, user=target, status=TeamMembershipStatus.ACTIVE).exists())
        self.assertTrue(can(target, PermissionCode.FINANCE_MANAGE, self.organization))
        self.assertFalse(can(target, PermissionCode.MARKETING_MANAGE, self.organization))

    def test_public_profile_is_visible_without_team_data(self):
        response = self.client.get(f"/o/{self.organization.slug}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Makolo Community Events")
        self.assertContains(response, "Community Day")
        self.assertNotContains(response, self.finance.email)
        self.assertNotContains(response, "Finance")

    def test_finance_role_can_confirm_manual_payment_and_refund(self):
        ticket_type = TicketType.objects.create(event=self.event, name="Finance Pass", price=Decimal("25.00"), currency="USD", quantity_total=10)
        order = create_order(buyer=self.buyer, event=self.event, customer_name="Buyer", customer_email=self.buyer.email, selections=[(ticket_type, 1)])
        payment = initiate_payment(order=order, actor=self.finance, provider=PaymentProvider.MANUAL, method="cash")
        complete_manual_payment(payment=payment, actor=self.finance, provider_reference="ORG-CASH-001")
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.SUCCEEDED)
        self.assertEqual(order.status, TicketOrderStatus.CONFIRMED)
        refund_payment(payment=payment, actor=self.finance, reason="Test finance organization")
        payment.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(payment.status, PaymentStatus.REFUNDED)
        self.assertEqual(order.status, TicketOrderStatus.CANCELLED)
