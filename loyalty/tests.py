from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization, OrganizationMembership, OrganizationRole
from promotions.models import DiscountType, Promotion
from tickets.models import TicketStatus, TicketType
from tickets.services import cancel_order, create_order

from .models import LedgerKind, LoyaltyAccount, LoyaltyLedgerEntry, LoyaltyProgram, LoyaltyReward, LoyaltyTier, MembershipPlan, MembershipStatus
from .services import activate_membership, adjust_points, award_checkin_points, expire_due_memberships, redeem_reward, request_membership


User = get_user_model()


class LoyaltyFixtureMixin:
    password = "Strong-loyalty-password-2026!"

    def build_fixture(self):
        self.owner = User.objects.create_user(username="loyalty-owner", email="owner@loyalty.test", password=self.password)
        self.marketing = User.objects.create_user(username="loyalty-marketing", email="marketing@loyalty.test", password=self.password)
        self.finance = User.objects.create_user(username="loyalty-finance", email="finance@loyalty.test", password=self.password)
        self.participant = User.objects.create_user(username="loyalty-member", email="member@loyalty.test", password=self.password)
        self.other = User.objects.create_user(username="loyalty-other", email="other@loyalty.test", password=self.password)
        self.organization = Organization.objects.create(name="Makolo Loyalty Club", created_by=self.owner)
        OrganizationMembership.objects.create(organization=self.organization, user=self.owner, role=OrganizationRole.OWNER)
        OrganizationMembership.objects.create(organization=self.organization, user=self.marketing, role=OrganizationRole.MARKETING)
        OrganizationMembership.objects.create(organization=self.organization, user=self.finance, role=OrganizationRole.FINANCE)
        self.program = LoyaltyProgram.objects.create(
            organization=self.organization,
            name="Makolo Club",
            points_per_order=10,
            points_per_ticket=5,
            points_per_checkin=20,
            created_by=self.owner,
        )
        self.base_tier = LoyaltyTier.objects.create(program=self.program, name="Bronze", code="BRONZE", threshold_points=0, points_multiplier=Decimal("1.00"))
        self.gold_tier = LoyaltyTier.objects.create(program=self.program, name="Gold", code="GOLD", threshold_points=100, points_multiplier=Decimal("1.50"))
        start = timezone.now() + timedelta(hours=2)
        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Makolo Loyalty Night",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=5),
            published_at=timezone.now(),
            capacity=100,
        )
        self.ticket_type = TicketType.objects.create(event=self.event, name="Standard", price=0, currency="USD", quantity_total=100)
        self.promotion = Promotion.objects.create(
            organization=self.organization,
            name="Member 10",
            discount_type=DiscountType.PERCENT,
            discount_value=Decimal("10.00"),
            created_by=self.owner,
        )


class LoyaltyServiceTests(LoyaltyFixtureMixin, TestCase):
    def setUp(self):
        self.build_fixture()

    def test_confirmed_order_awards_points_once(self):
        order = create_order(
            buyer=self.participant,
            event=self.event,
            customer_name="Member",
            customer_email=self.participant.email,
            selections=[(self.ticket_type, 2)],
        )
        account = LoyaltyAccount.objects.get(program=self.program, user=self.participant)
        self.assertEqual(account.points_balance, 20)
        self.assertEqual(account.current_tier, self.base_tier)
        order.save()
        account.refresh_from_db()
        self.assertEqual(account.points_balance, 20)
        self.assertEqual(LoyaltyLedgerEntry.objects.filter(idempotency_key=f"order:{order.pk}").count(), 1)

    def test_cancelled_confirmed_order_reverses_purchase_points(self):
        order = create_order(
            buyer=self.participant,
            event=self.event,
            customer_name="Member",
            customer_email=self.participant.email,
            selections=[(self.ticket_type, 1)],
        )
        cancel_order(order=order, actor=self.owner)
        account = LoyaltyAccount.objects.get(program=self.program, user=self.participant)
        self.assertEqual(account.points_balance, 0)
        self.assertTrue(LoyaltyLedgerEntry.objects.filter(kind=LedgerKind.ORDER_REVERSAL, order=order).exists())

    def test_checkin_awards_points_to_current_owner_once(self):
        order = create_order(
            buyer=self.participant,
            event=self.event,
            customer_name="Member",
            customer_email=self.participant.email,
            selections=[(self.ticket_type, 1)],
        )
        ticket = order.tickets.get()
        ticket.status = TicketStatus.USED
        ticket.used_at = timezone.now()
        ticket.save(update_fields=["status", "used_at", "updated_at"])
        account = LoyaltyAccount.objects.get(program=self.program, user=self.participant)
        self.assertEqual(account.points_balance, 35)
        ticket.save()
        account.refresh_from_db()
        self.assertEqual(account.points_balance, 35)

    def test_free_membership_activates_and_grants_bonus_and_private_code(self):
        plan = MembershipPlan.objects.create(
            program=self.program,
            name="Club Free",
            code="FREE",
            price=0,
            currency="USD",
            duration_days=30,
            points_multiplier=Decimal("2.00"),
            join_bonus_points=40,
            benefit_promotion=self.promotion,
            created_by=self.owner,
        )
        subscription = request_membership(user=self.participant, plan=plan)
        self.assertEqual(subscription.status, MembershipStatus.ACTIVE)
        self.assertEqual(subscription.activation_source, "free")
        self.assertIsNotNone(subscription.benefit_code_id)
        self.assertTrue(subscription.benefit_code.is_private)
        self.assertEqual(subscription.benefit_code.max_redemptions, 1)
        account = LoyaltyAccount.objects.get(program=self.program, user=self.participant)
        self.assertEqual(account.points_balance, 40)

    def test_paid_membership_requires_finance_activation(self):
        plan = MembershipPlan.objects.create(program=self.program, name="Premium", code="PREMIUM", price=Decimal("50.00"), currency="USD", created_by=self.owner)
        subscription = request_membership(user=self.participant, plan=plan)
        self.assertEqual(subscription.status, MembershipStatus.PENDING)
        with self.assertRaises(PermissionDenied):
            activate_membership(subscription=subscription, actor=self.marketing)
        subscription = activate_membership(subscription=subscription, actor=self.finance)
        self.assertEqual(subscription.status, MembershipStatus.ACTIVE)
        self.assertEqual(subscription.activation_source, "manual")

    def test_membership_and_tier_multipliers_are_applied_at_earning_time(self):
        account = LoyaltyAccount.objects.create(program=self.program, user=self.participant, points_balance=100, lifetime_earned=100, current_tier=self.gold_tier)
        plan = MembershipPlan.objects.create(program=self.program, name="Plus", code="PLUS", price=0, currency="USD", points_multiplier=Decimal("2.00"), created_by=self.owner)
        request_membership(user=self.participant, plan=plan)
        order = create_order(
            buyer=self.participant,
            event=self.event,
            customer_name="Member",
            customer_email=self.participant.email,
            selections=[(self.ticket_type, 1)],
        )
        account.refresh_from_db()
        self.assertEqual(account.points_balance, 145)
        entry = LoyaltyLedgerEntry.objects.get(idempotency_key=f"order:{order.pk}")
        self.assertEqual(entry.points, 45)

    def test_reward_redemption_deducts_points_and_creates_one_use_code(self):
        account = LoyaltyAccount.objects.create(program=self.program, user=self.participant, points_balance=120, lifetime_earned=120, current_tier=self.gold_tier)
        reward = LoyaltyReward.objects.create(
            program=self.program,
            name="Remise membre",
            points_cost=50,
            promotion=self.promotion,
            max_redemptions_per_member=1,
            created_by=self.owner,
        )
        redemption = redeem_reward(user=self.participant, reward=reward)
        account.refresh_from_db()
        self.assertEqual(account.points_balance, 70)
        self.assertEqual(account.lifetime_redeemed, 50)
        self.assertTrue(redemption.promotion_code.is_private)
        self.assertEqual(redemption.promotion_code.max_redemptions, 1)
        with self.assertRaises(ValidationError):
            redeem_reward(user=self.participant, reward=reward)

    def test_reward_requires_sufficient_points(self):
        LoyaltyAccount.objects.create(program=self.program, user=self.participant, points_balance=5)
        reward = LoyaltyReward.objects.create(program=self.program, name="VIP", points_cost=50, created_by=self.owner)
        with self.assertRaises(ValidationError):
            redeem_reward(user=self.participant, reward=reward)

    def test_marketing_can_adjust_points_but_finance_cannot(self):
        account = LoyaltyAccount.objects.create(program=self.program, user=self.participant)
        adjust_points(actor=self.marketing, account=account, points=25, reason="Geste fidélité")
        account.refresh_from_db()
        self.assertEqual(account.points_balance, 25)
        with self.assertRaises(PermissionDenied):
            adjust_points(actor=self.finance, account=account, points=10, reason="No")

    def test_expired_membership_deactivates_benefit_code(self):
        plan = MembershipPlan.objects.create(program=self.program, name="Short", code="SHORT", price=0, currency="USD", duration_days=1, benefit_promotion=self.promotion, created_by=self.owner)
        subscription = request_membership(user=self.participant, plan=plan)
        subscription.ends_at = timezone.now() - timedelta(minutes=1)
        subscription.save(update_fields=["ends_at", "updated_at"])
        self.assertEqual(expire_due_memberships(), 1)
        subscription.refresh_from_db()
        subscription.benefit_code.refresh_from_db()
        self.assertEqual(subscription.status, MembershipStatus.EXPIRED)
        self.assertFalse(subscription.benefit_code.is_active)


class LoyaltyApiTests(LoyaltyFixtureMixin, APITestCase):
    def setUp(self):
        self.build_fixture()

    def test_participant_can_join_free_plan_and_read_only_own_account(self):
        plan = MembershipPlan.objects.create(program=self.program, name="Free", code="FREE", price=0, currency="USD", join_bonus_points=10, created_by=self.owner)
        self.client.force_authenticate(self.participant)
        response = self.client.post("/api/v1/loyalty/memberships/join/", {"plan_id": str(plan.pk)}, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        response = self.client.get("/api/v1/loyalty/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["accounts"]), 1)
        self.assertEqual(response.data["accounts"][0]["points_balance"], 10)

    def test_marketing_can_create_program_for_other_org_but_finance_cannot(self):
        other_org = Organization.objects.create(name="Second Loyalty Org", created_by=self.owner)
        OrganizationMembership.objects.create(organization=other_org, user=self.marketing, role=OrganizationRole.MARKETING)
        OrganizationMembership.objects.create(organization=other_org, user=self.finance, role=OrganizationRole.FINANCE)
        payload = {"organization_id": str(other_org.pk), "name": "Second Club"}
        self.client.force_authenticate(self.finance)
        denied = self.client.post("/api/v1/loyalty/programs/", payload, format="json")
        self.assertEqual(denied.status_code, status.HTTP_403_FORBIDDEN)
        self.client.force_authenticate(self.marketing)
        created = self.client.post("/api/v1/loyalty/programs/", payload, format="json")
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)

    def test_finance_can_activate_paid_membership(self):
        plan = MembershipPlan.objects.create(program=self.program, name="Paid", code="PAID", price=Decimal("15.00"), currency="USD", created_by=self.owner)
        subscription = request_membership(user=self.participant, plan=plan)
        self.client.force_authenticate(self.finance)
        response = self.client.post(f"/api/v1/loyalty/memberships/{subscription.pk}/activate/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], MembershipStatus.ACTIVE)

    def test_public_program_api_contains_no_other_member_pii(self):
        LoyaltyAccount.objects.create(program=self.program, user=self.participant, points_balance=80)
        self.client.force_authenticate(self.other)
        response = self.client.get(f"/api/v1/loyalty/organizations/{self.organization.slug}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rendered = str(response.data)
        self.assertNotIn(self.participant.email, rendered)
