"""Owner valuation and two-level Appuis spending without financial promises."""
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from authorization.constants import PermissionCode
from organizations.models import Organization
from recognition.models import (
    RecognitionAccount, RecognitionCreditValuation, RecognitionRedemption,
    RewardDefinition, RewardKind,
)
from recognition.valuation import credit_money_equivalent
from subscriptions.models import FeatureDefinition
from recognition.governance_services import configure_credit_valuation


class AppuisCreditValuationTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.operator = users.objects.create_superuser(
            username="appuis-value-operator", email="value@example.test",
            password="only-in-test-value!",
        )
        self.viewer = users.objects.create_user(
            username="appuis-value-viewer", password="only-in-test-value!",
        )
        self.space = Organization.objects.create(
            name="Space Credit Test", created_by=self.operator,
        )
        self.account = RecognitionAccount.objects.create(
            profile=self.operator, points_balance=240, pending_points=35,
            lifetime_earned=275,
        )

    def test_unconfigured_or_disabled_rate_does_not_create_money(self):
        self.assertIsNone(credit_money_equivalent(self.account))
        self.client.force_login(self.operator)
        response = self.client.get(reverse("recognition_api:me"))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()["monetary_equivalent"])
        self.assertNotContains(
            self.client.get(reverse("core:participant-appuis-use")),
            "Retirer",
        )

    def test_configured_value_excludes_pending_and_hides_rate(self):
        RecognitionCreditValuation.objects.create(
            pk=1, currency="USD", amount_per_credit=Decimal("0.05000000"),
            is_active=True,
        )
        self.assertEqual(
            credit_money_equivalent(self.account),
            {"amount": "12.00", "currency": "USD"},
        )
        self.client.force_login(self.operator)
        data = self.client.get(reverse("recognition_api:me")).json()
        self.assertEqual(data["monetary_equivalent"]["amount"], "12.00")
        self.assertNotIn("amount_per_credit", str(data))
        main = self.client.get(reverse("core:participant-appuis"))
        self.assertNotContains(main, "12.00")
        spending = self.client.get(reverse("core:participant-appuis-use"))
        self.assertContains(spending, "12.00")
        self.assertContains(spending, "USD")
        self.assertContains(spending, 'disabled aria-disabled="true"')

    def test_no_money_for_zero_available_even_with_pending(self):
        RecognitionCreditValuation.objects.create(
            pk=1, currency="CDF", amount_per_credit=Decimal("100"),
            is_active=True,
        )
        self.account.points_balance = 0
        self.account.save(update_fields=["points_balance"])
        self.assertIsNone(credit_money_equivalent(self.account))

    def test_platform_change_is_audited_and_version_checked(self):
        config = configure_credit_valuation(
            actor=self.operator, expected_version="0",
            amount_per_credit="0.05", currency="USD",
            activate=True, reason="Validation du barème de test",
        )
        self.assertTrue(config.is_active)
        self.assertEqual(config.version, 1)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            configure_credit_valuation(
                actor=self.operator, expected_version="0",
                amount_per_credit="0.09", currency="USD",
                activate=True, reason="Décision concurrente refusée",
            )
        config = configure_credit_valuation(
            actor=self.operator, expected_version="1",
            amount_per_credit="0.05", currency="USD",
            activate=False, reason="Suspension de la valorisation",
        )
        self.assertFalse(config.is_active)
        self.assertIsNone(credit_money_equivalent(self.account))

    def test_non_operator_cannot_set_rate(self):
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):
            configure_credit_valuation(
                actor=self.viewer, expected_version="0",
                amount_per_credit="1", currency="USD",
                activate=True, reason="Tentative non autorisée",
            )

    def test_web_credit_spend_uses_existing_recognition_owner_idempotently(self):
        reward = RewardDefinition.objects.create(
            code="appuis-usable", version=1, name="Avantage réel",
            points_cost=25, kind=RewardKind.OTHER,
            fulfillment={"owner_domain": "external"},
        )
        RewardDefinition.objects.create(
            code="appuis-payout-disabled", version=1, name="Retrait expérimental",
            points_cost=40, kind=RewardKind.PAYOUT,
            fulfillment={"amount": "4.00", "currency": "USD"},
        )
        self.client.force_login(self.operator)
        route = reverse("core:participant-appuis-use")
        read = self.client.get(route)
        self.assertContains(read, "Avantage réel")
        self.assertNotContains(read, "Retrait expérimental")
        key = str(uuid.uuid4())
        first = self.client.post(route, {
            "reward_id": str(reward.pk), "intent_key": key,
        })
        self.assertEqual(first.status_code, 302)
        self.account.refresh_from_db()
        self.assertEqual(self.account.points_balance, 215)
        repeat = self.client.post(route, {
            "reward_id": str(reward.pk), "intent_key": key,
        })
        self.assertEqual(repeat.status_code, 302)
        self.account.refresh_from_db()
        self.assertEqual(self.account.points_balance, 215)
        self.assertEqual(
            RecognitionRedemption.objects.filter(owner_account=self.account).count(),
            1,
        )

    def test_platform_operator_form_configures_only_display_and_is_private(self):
        self.client.force_login(self.operator)
        url = reverse("platform_web:recognition-credit-valuation")
        read = self.client.get(reverse("platform_web:recognition"))
        self.assertEqual(read.status_code, 200)
        self.assertContains(read, "Montant par crédit")
        response = self.client.post(url, {
            "currency": "USD",
            "amount_per_credit": "0.05",
            "expected_version": "0",
            "active": "1",
            "reason": "Configuration test approuvée",
            "confirm": "1",
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            RecognitionCreditValuation.objects.get(pk=1).is_active
        )
        self.assertEqual(
            self.client.get(reverse("core:participant-appuis-use"))["Cache-Control"],
            "private, no-store",
        )
        self.assertEqual(
            self.client.get(reverse("recognition_api:me"))["Cache-Control"],
            "private, no-store",
        )

    def test_verified_feature_is_individually_labeled_not_a_fake_subscription(self):
        feature = FeatureDefinition.objects.create(
            code="recognition.appuis.unlock", name="Fonctionnalité réelle",
            domain="recognition", value_type="boolean",
            supports_profile=True, supports_space=False,
            aggregation_strategy="BOOLEAN_OR",
            enforcement_policy="feature_gate",
        )
        RewardDefinition.objects.create(
            code="appuis-unlock-real", version=1,
            name="Déblocage utile", kind=RewardKind.ENTITLEMENT,
            points_cost=80, fulfillment={
                "feature_code": feature.code,
                "duration_days": 30,
            },
        )
        self.client.force_login(self.operator)
        data = self.client.get(reverse("recognition_api:me")).json()
        row = next(row for row in data["rewards"]
                   if row["name"] == "Déblocage utile")
        self.assertEqual(row["presentation"], {
            "category": "feature",
            "action": "Débloquer",
            "duration_days": 30,
        })
        self.assertNotIn("feature_code", str(row))
        page = self.client.get(reverse("core:participant-appuis-use"))
        self.assertContains(page, "Fonctionnalités")
        self.assertContains(page, "Déblocage utile")
        self.assertNotContains(page, "Abonnements")


    def test_spending_space_without_view_permission_does_not_expose_account(self):
        space_account = RecognitionAccount.objects.create(
            space=self.space, points_balance=55,
        )
        self.client.force_login(self.viewer)
        response = self.client.get(reverse(
            "organizations:space-us-appuis-use",
            kwargs={"slug": self.space.slug},
        ))
        self.assertIn(response.status_code, {403, 404})
        self.assertNotContains(response, "55 crédits", status_code=response.status_code)
        self.assertEqual(space_account.points_balance, 55)
