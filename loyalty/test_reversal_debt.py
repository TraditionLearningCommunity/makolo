from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility
from organizations.models import Organization, OrganizationMembership, OrganizationRole
from tickets.models import TicketType
from tickets.services import cancel_order, create_order

from .models import LoyaltyAccount, LoyaltyLedgerEntry, LoyaltyProgram, LoyaltyReward
from .services import redeem_reward


User = get_user_model()


class LoyaltyReversalDebtTests(TestCase):
    def test_cancellation_reverses_full_order_points_even_after_reward_spend(self):
        owner = User.objects.create_user(
            username="debt-owner",
            email="debt-owner@example.com",
            password="Strong-debt-owner-2026!",
        )
        participant = User.objects.create_user(
            username="debt-member",
            email="debt-member@example.com",
            password="Strong-debt-member-2026!",
        )
        organization = Organization.objects.create(
            name="Debt-safe Loyalty Org",
            created_by=owner,
        )
        OrganizationMembership.objects.create(
            organization=organization,
            user=owner,
            role=OrganizationRole.OWNER,
        )
        program = LoyaltyProgram.objects.create(
            organization=organization,
            points_per_order=10,
            points_per_ticket=5,
            points_per_checkin=0,
            created_by=owner,
        )
        reward = LoyaltyReward.objects.create(
            program=program,
            name="Petite récompense",
            points_cost=10,
            max_redemptions_per_member=1,
            created_by=owner,
        )
        start = timezone.now() + timedelta(hours=2)
        event = Event.objects.create(
            organizer=owner,
            organization=organization,
            title="Debt-safe Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=4),
            published_at=timezone.now(),
            capacity=20,
        )
        ticket_type = TicketType.objects.create(
            event=event,
            name="Free",
            price=0,
            currency="USD",
            quantity_total=20,
        )

        order = create_order(
            buyer=participant,
            event=event,
            customer_name="Debt Member",
            customer_email=participant.email,
            selections=[(ticket_type, 1)],
        )
        account = LoyaltyAccount.objects.get(program=program, user=participant)
        self.assertEqual(account.points_balance, 15)

        redeem_reward(user=participant, reward=reward)
        account.refresh_from_db()
        self.assertEqual(account.points_balance, 5)

        cancel_order(order=order, actor=owner)
        account.refresh_from_db()

        self.assertEqual(account.points_balance, -10)
        self.assertEqual(account.lifetime_earned, 0)
        reversal = LoyaltyLedgerEntry.objects.get(idempotency_key=f"order-reversal:{order.pk}")
        self.assertEqual(reversal.points, -15)
