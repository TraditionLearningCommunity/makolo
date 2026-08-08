from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from events.models import Event, EventStatus, EventVisibility
from notifications.models import Notification
from organizations.models import Organization, OrganizationMembership, OrganizationRole
from payments.models import PaymentMethod, PaymentProvider
from payments.services import complete_sandbox_payment, initiate_payment
from tickets.models import TicketType
from tickets.services import create_order

from .models import AffiliateCampaign, CampaignStatus, CommissionType, Partner, ReferralCode
from .services import attribute_order, create_payout, mark_payout_paid


User = get_user_model()


@override_settings(PAYMENTS_SANDBOX_ENABLED=True)
class PartnerNotificationTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="notify-partner-owner", email="notify-owner@example.com", password="Strong-password-2026!", is_verified=True)
        self.finance = User.objects.create_user(username="notify-partner-finance", email="notify-finance@example.com", password="Strong-password-2026!", is_verified=True)
        self.ambassador = User.objects.create_user(username="notify-ambassador", email="notify-ambassador@example.com", password="Strong-password-2026!", is_verified=True)
        self.buyer = User.objects.create_user(username="notify-affiliate-buyer", email="notify-buyer@example.com", password="Strong-password-2026!", is_verified=True)
        self.organization = Organization.objects.create(name="Partner Notification Org", created_by=self.owner)
        OrganizationMembership.objects.create(organization=self.organization, user=self.owner, role=OrganizationRole.OWNER)
        OrganizationMembership.objects.create(organization=self.organization, user=self.finance, role=OrganizationRole.FINANCE)
        start = timezone.now() + timedelta(days=7)
        self.event = Event.objects.create(
            organizer=self.owner,
            organization=self.organization,
            title="Partner Notification Event",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=2),
            published_at=timezone.now(),
        )
        self.ticket_type = TicketType.objects.create(event=self.event, name="Standard", price=Decimal("20.00"), currency="USD", quantity_total=50)
        self.partner = Partner.objects.create(
            organization=self.organization,
            user=self.ambassador,
            name="Notification Ambassador",
            email=self.ambassador.email,
            created_by=self.owner,
        )
        self.campaign = AffiliateCampaign.objects.create(
            organization=self.organization,
            event=self.event,
            name="Notification Campaign",
            status=CampaignStatus.ACTIVE,
            commission_type=CommissionType.PERCENTAGE,
            commission_value=Decimal("10.00"),
            created_by=self.owner,
        )

    def test_new_code_notifies_linked_ambassador_after_commit(self):
        with self.captureOnCommitCallbacks(execute=True):
            code = ReferralCode.objects.create(campaign=self.campaign, partner=self.partner, code="NOTIFY10")
        notification = Notification.objects.get(dedup_key=f"partner-code-created:{code.pk}")
        self.assertEqual(notification.recipient, self.ambassador)
        self.assertIn("lien ambassadeur", notification.title.lower())

    def test_commission_and_paid_payout_notify_ambassador(self):
        with self.captureOnCommitCallbacks(execute=True):
            code = ReferralCode.objects.create(campaign=self.campaign, partner=self.partner, code="EARN10")
        order = create_order(
            buyer=self.buyer,
            event=self.event,
            customer_name="Notification Buyer",
            customer_email=self.buyer.email,
            selections=[(self.ticket_type, 1)],
        )
        attribute_order(order=order, referral_code=code)
        payment = initiate_payment(order=order, actor=self.buyer, provider=PaymentProvider.SANDBOX, method=PaymentMethod.CARD)
        with self.captureOnCommitCallbacks(execute=True):
            complete_sandbox_payment(payment=payment, actor=self.buyer)
        commission_notice = Notification.objects.filter(
            recipient=self.ambassador,
            dedup_key__startswith="partner-commission-earned:",
        ).first()
        self.assertIsNotNone(commission_notice)
        self.assertIn("2.00 USD", commission_notice.message)

        payout = create_payout(partner=self.partner, actor=self.finance, currency="USD")
        with self.captureOnCommitCallbacks(execute=True):
            payout = mark_payout_paid(payout=payout, actor=self.finance, reference="PAY-NOTIFY-001")
        payout_notice = Notification.objects.get(dedup_key=f"partner-payout-paid:{payout.pk}")
        self.assertEqual(payout_notice.recipient, self.ambassador)
        self.assertIn("PAY-NOTIFY-001", payout_notice.message)
