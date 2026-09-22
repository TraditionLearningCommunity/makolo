from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from rest_framework.test import APIClient

from accounts.models import User
from events.models import Event, EventStatus, EventVisibility
from loyalty.models import LoyaltyAccount, LoyaltyProgram, LoyaltyReward, MembershipPlan
from organizations.console_context import authorized_spaces
from organizations.models import Organization
from partners.models import (
    AffiliateCampaign,
    CampaignStatus,
    CommissionType,
    Partner,
    PartnerPayout,
    PartnerStatus,
    PayoutStatus,
    ReferralCode,
)
from recognition.models import RecognitionLedgerEntry
from recognition.services import get_or_create_account


PASSWORD = "Makolo!2026-Z9-ValueA8"


class Z9MobilizableValueAPIContractTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="z9-value-user",
            email="z9-value-user@makolo.test",
            password=PASSWORD,
        )
        self.other = User.objects.create_user(
            username="z9-value-other",
            email="z9-value-other@makolo.test",
            password=PASSWORD,
        )
        self.client.force_authenticate(self.user)
        self.org = Organization.objects.create(
            name="Organisation Z9",
            slug="organisation-z9",
            created_by=self.other,
        )

    def test_recognition_read_is_side_effect_free_and_history_is_human_safe(self):
        empty = self.client.get("/api/v1/recognition/me/")
        self.assertEqual(empty.status_code, 200)
        self.assertIsNone(empty.json()["account"])

        account = get_or_create_account(profile=self.user)
        account.points_balance = 30
        account.lifetime_earned = 30
        account.save(update_fields=["points_balance", "lifetime_earned", "updated_at"])
        entry = RecognitionLedgerEntry.objects.create(
            account=account,
            kind="grant",
            points=30,
            description="Contribution reconnue",
            idempotency_key="z9-recognition-grant",
            metadata={"internal_event_id": "secret-internal-z9"},
        )

        response = self.client.get("/api/v1/recognition/me/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["summary"]["unit"], "recognition_credit")
        self.assertFalse(data["summary"]["is_currency"])
        self.assertEqual(data["summary"]["available_credits"], 30)
        self.assertEqual(data["recent_activity"][0]["id"], str(entry.pk))
        serialized = str(data)
        self.assertNotIn("secret-internal-z9", serialized)
        self.assertNotIn("idempotency_key", serialized)
        self.assertNotIn("metadata", data["recent_activity"][0])

    def test_recognition_other_profile_never_leaks(self):
        other_account = get_or_create_account(profile=self.other)
        other_account.points_balance = 999
        other_account.lifetime_earned = 999
        other_account.save(
            update_fields=["points_balance", "lifetime_earned", "updated_at"]
        )
        RecognitionLedgerEntry.objects.create(
            account=other_account,
            kind="grant",
            points=999,
            description="Foreign recognition sentinel",
            idempotency_key="z9-recognition-foreign",
        )

        response = self.client.get("/api/v1/recognition/me/")
        self.assertNotIn("Foreign recognition sentinel", str(response.json()))
        self.assertNotIn(str(other_account.pk), str(response.json()))

    def test_loyalty_programs_remain_distinct_and_get_creates_nothing(self):
        before = LoyaltyAccount.objects.filter(user=self.user).count()
        first = self.client.get("/api/v1/loyalty/me/")
        self.assertEqual(first.status_code, 200)
        self.assertEqual(LoyaltyAccount.objects.filter(user=self.user).count(), before)

        program_a = LoyaltyProgram.objects.create(
            organization=self.org,
            name="Programme A",
            points_name="étoiles",
            created_by=self.other,
        )
        org_b = Organization.objects.create(
            name="Organisation B Z9",
            slug="organisation-b-z9",
            created_by=self.other,
        )
        program_b = LoyaltyProgram.objects.create(
            organization=org_b,
            name="Programme B",
            points_name="jetons",
            created_by=self.other,
        )
        LoyaltyAccount.objects.create(program=program_a, user=self.user, points_balance=20)
        LoyaltyAccount.objects.create(program=program_b, user=self.user, points_balance=40)

        response = self.client.get("/api/v1/loyalty/me/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["summary"]["program_count"], 2)
        self.assertIsNone(data["summary"]["aggregate_points"])
        self.assertEqual(
            {(row["program_name"], row["points_name"], row["points_balance"]) for row in data["accounts"]},
            {("Programme A", "étoiles", 20), ("Programme B", "jetons", 40)},
        )
        self.assertNotIn("total_value", str(data))
        self.assertNotIn("wallet", str(data).lower())

    def test_loyalty_reward_capability_respects_owner_service_preconditions(self):
        program = LoyaltyProgram.objects.create(
            organization=self.org,
            name="Programme Rewards Z9",
            created_by=self.other,
        )
        LoyaltyAccount.objects.create(
            program=program,
            user=self.user,
            points_balance=100,
            lifetime_earned=100,
        )
        available = LoyaltyReward.objects.create(
            program=program,
            name="Avantage disponible",
            points_cost=20,
            created_by=self.other,
        )
        LoyaltyReward.objects.create(
            program=program,
            name="Avantage expiré",
            points_cost=10,
            ends_at=timezone.now() - timedelta(minutes=1),
            created_by=self.other,
        )
        LoyaltyReward.objects.create(
            program=program,
            name="Avantage trop cher",
            points_cost=1000,
            created_by=self.other,
        )

        data = self.client.get("/api/v1/loyalty/me/").json()
        self.assertEqual(
            [row["id"] for row in data["available_rewards"]],
            [str(available.pk)],
        )
        self.assertEqual(data["available_rewards"][0]["capabilities"], ["redeem"])

    def test_loyalty_membership_does_not_grant_space_authority(self):
        program = LoyaltyProgram.objects.create(
            organization=self.org,
            name="Programme Membership Z9",
            created_by=self.other,
        )
        plan = MembershipPlan.objects.create(
            program=program,
            name="Club Z9",
            code="CLUB-Z9",
            price=Decimal("0.00"),
            created_by=self.other,
        )
        joined = self.client.post(
            "/api/v1/loyalty/memberships/join/",
            {"plan_id": str(plan.pk)},
            format="json",
        )
        self.assertEqual(joined.status_code, 201)
        self.assertNotIn(self.org.pk, set(authorized_spaces(self.user).values_list("pk", flat=True)))

    def test_partner_collection_links_to_private_depth_without_granting_authority(self):
        mine = Partner.objects.create(
            organization=self.org,
            user=self.user,
            name="Partenaire personnel Z9",
            status=PartnerStatus.ACTIVE,
        )
        foreign = Partner.objects.create(
            organization=self.org,
            user=self.other,
            name="Partenaire étranger Z9",
            status=PartnerStatus.ACTIVE,
        )

        collection = self.client.get("/api/v1/me/partners/")
        self.assertEqual(collection.status_code, 200)
        relationships = collection.json()["data"]["relationships"]["items"]
        self.assertEqual([row["id"] for row in relationships], [str(mine.pk)])
        self.assertEqual(
            relationships[0]["links"]["detail"],
            f"/api/v1/me/partners/{mine.pk}/",
        )

        detail = self.client.get(f"/api/v1/me/partners/{mine.pk}/")
        self.assertEqual(detail.status_code, 200)
        data = detail.json()["data"]
        self.assertFalse(data["relationship"]["authority"]["space_authority_granted"])
        self.assertNotIn(self.org.pk, set(authorized_spaces(self.user).values_list("pk", flat=True)))

        denied = self.client.get(f"/api/v1/me/partners/{foreign.pk}/")
        self.assertEqual(denied.status_code, 404)
        self.assertNotIn("Partenaire étranger Z9", str(detail.json()))

    def test_partner_codes_are_subject_scoped_and_private_partner_fields_stay_hidden(self):
        mine = Partner.objects.create(
            organization=self.org,
            user=self.user,
            name="Partner internal legal name Z9",
            public_label="Ambassadeur Z9",
            email="private-partner-z9@example.test",
            phone="+243000000000",
            notes="CRM-like private note sentinel Z9",
            status=PartnerStatus.ACTIVE,
        )
        foreign = Partner.objects.create(
            organization=self.org,
            user=self.other,
            name="Partner code foreign Z9",
            status=PartnerStatus.ACTIVE,
        )
        start = timezone.now() + timedelta(hours=2)
        event = Event.objects.create(
            organizer=self.other,
            organization=self.org,
            title="Event code Z9",
            status=EventStatus.PUBLISHED,
            visibility=EventVisibility.PUBLIC,
            start_at=start,
            end_at=start + timedelta(hours=2),
            published_at=timezone.now(),
            capacity=20,
        )
        campaign = AffiliateCampaign.objects.create(
            organization=self.org,
            event=event,
            name="Campagne Z9",
            status=CampaignStatus.ACTIVE,
            commission_type=CommissionType.PERCENTAGE,
            commission_value=Decimal("10.00"),
            starts_at=timezone.now() - timedelta(minutes=1),
            ends_at=timezone.now() + timedelta(days=2),
            created_by=self.other,
        )
        mine_code = ReferralCode.objects.create(
            campaign=campaign,
            partner=mine,
            code="MINE-Z9",
        )
        # A second campaign is required by the canonical one-code-per-campaign/partner rule.
        foreign_campaign = AffiliateCampaign.objects.create(
            organization=self.org,
            event=event,
            name="Campagne étrangère Z9",
            status=CampaignStatus.ACTIVE,
            commission_type=CommissionType.PERCENTAGE,
            commission_value=Decimal("5.00"),
            starts_at=timezone.now() - timedelta(minutes=1),
            ends_at=timezone.now() + timedelta(days=2),
            created_by=self.other,
        )
        ReferralCode.objects.create(
            campaign=foreign_campaign,
            partner=foreign,
            code="FOREIGN-Z9",
        )

        data = self.client.get(f"/api/v1/me/partners/{mine.pk}/").json()["data"]
        self.assertEqual([row["id"] for row in data["codes"]["items"]], [str(mine_code.pk)])
        serialized = str(data)
        self.assertIn("MINE-Z9", serialized)
        self.assertNotIn("FOREIGN-Z9", serialized)
        self.assertNotIn("private-partner-z9@example.test", serialized)
        self.assertNotIn("+243000000000", serialized)
        self.assertNotIn("CRM-like private note sentinel Z9", serialized)

    def test_partner_money_keeps_currencies_and_states_separate(self):
        mine = Partner.objects.create(
            organization=self.org,
            user=self.user,
            name="Partenaire paiements Z9",
            status=PartnerStatus.ACTIVE,
        )
        usd = PartnerPayout.objects.create(
            organization=self.org,
            partner=mine,
            currency="USD",
            amount=Decimal("10.00"),
            status=PayoutStatus.DRAFT,
            created_by=self.other,
        )
        cdf = PartnerPayout.objects.create(
            organization=self.org,
            partner=mine,
            currency="CDF",
            amount=Decimal("20000.00"),
            status=PayoutStatus.PAID,
            created_by=self.other,
            paid_by=self.other,
            paid_at=timezone.now(),
        )

        data = self.client.get(f"/api/v1/me/partners/{mine.pk}/").json()["data"]
        payouts = {row["currency"]: row for row in data["payouts"]["items"]}
        self.assertEqual(payouts["USD"]["state"], PayoutStatus.DRAFT)
        self.assertEqual(payouts["CDF"]["state"], PayoutStatus.PAID)
        self.assertEqual(payouts["USD"]["amount"], "10.00")
        self.assertEqual(payouts["CDF"]["amount"], "20000.00")
        self.assertIsNone(data["economic_state"]["aggregate_across_currencies"])
        self.assertNotIn("total_value", str(data))

    def test_personal_z9_gets_do_not_create_domain_truth(self):
        before = {
            "recognition": self.user.recognition_accounts.count(),
            "loyalty": LoyaltyAccount.objects.filter(user=self.user).count(),
            "partner": Partner.objects.filter(user=self.user).count(),
        }
        self.client.get("/api/v1/recognition/me/")
        self.client.get("/api/v1/loyalty/me/")
        self.client.get("/api/v1/me/partners/")
        after = {
            "recognition": self.user.recognition_accounts.count(),
            "loyalty": LoyaltyAccount.objects.filter(user=self.user).count(),
            "partner": Partner.objects.filter(user=self.user).count(),
        }
        self.assertEqual(before, after)
