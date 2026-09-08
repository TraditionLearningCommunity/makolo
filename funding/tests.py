from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from activities.models import ActivityStatus, ActivityVisibility
from payments.models import PaymentObligationStatus
from payments.obligation_services import refund_payment_obligation, satisfy_payment_obligation

from .models import FundingDetails
from .selectors import funding_progress
from .services import create_funding, create_funding_contribution


User = get_user_model()


class FundingCoreTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(email="funding-owner@example.test", username="funding-owner", password="test-pass")
        self.contributor = User.objects.create_user(email="funding-contributor@example.test", username="funding-contributor", password="test-pass")
        self.funding = create_funding(
            actor=self.owner,
            title="Financer la scène",
            description="Réunir les moyens nécessaires pour installer la scène.",
            currency="USD",
            target_amount=Decimal("100.00"),
            minimum_contribution=Decimal("2.00"),
            status=ActivityStatus.PUBLISHED,
            visibility=ActivityVisibility.PUBLIC,
        )

    def test_activity_remains_generic_and_funding_keeps_only_financing_facts(self):
        self.assertEqual(self.funding.activity.title, "Financer la scène")
        self.assertEqual(self.funding.activity.funding_details, self.funding)
        self.assertEqual(self.funding.target_amount, Decimal("100.00"))
        self.assertFalse(hasattr(self.funding, "title"))

    def test_progress_is_derived_from_satisfied_obligations_and_never_negative(self):
        first = create_funding_contribution(
            funding=self.funding,
            actor=self.contributor,
            amount=Decimal("40.00"),
            client_reference="first",
        )
        self.assertEqual(funding_progress(self.funding).raised_amount, Decimal("0.00"))
        satisfy_payment_obligation(obligation=first.payment_obligation, source="funding-test")
        progress = funding_progress(self.funding)
        self.assertEqual(progress.raised_amount, Decimal("40.00"))
        self.assertEqual(progress.remaining_amount, Decimal("60.00"))
        self.assertFalse(progress.target_reached)

        second = create_funding_contribution(
            funding=self.funding,
            actor=self.owner,
            amount=Decimal("75.00"),
            client_reference="second",
        )
        satisfy_payment_obligation(obligation=second.payment_obligation, source="funding-test")
        progress = funding_progress(self.funding)
        self.assertEqual(progress.raised_amount, Decimal("115.00"))
        self.assertEqual(progress.remaining_amount, Decimal("0.00"))
        self.assertEqual(progress.exceeded_amount, Decimal("15.00"))
        self.assertTrue(progress.target_reached)

        refund_payment_obligation(obligation=second.payment_obligation)
        progress = funding_progress(self.funding)
        self.assertEqual(progress.raised_amount, Decimal("40.00"))
        self.assertEqual(progress.remaining_amount, Decimal("60.00"))

    def test_no_target_funding_exposes_raised_amount_without_fake_remaining(self):
        no_target = create_funding(
            actor=self.owner,
            title="Soutenir le programme",
            currency="USD",
            target_amount=None,
            status=ActivityStatus.PUBLISHED,
        )
        progress = funding_progress(no_target)
        self.assertIsNone(progress.target_amount)
        self.assertIsNone(progress.remaining_amount)
        self.assertIsNone(progress.exceeded_amount)
        self.assertIsNone(progress.percent_reached)

    def test_contribution_builds_one_canonical_payment_obligation_and_is_idempotent(self):
        contribution = create_funding_contribution(
            funding=self.funding,
            actor=self.contributor,
            amount="12.50",
            client_reference="browser-123",
        )
        again = create_funding_contribution(
            funding=self.funding,
            actor=self.contributor,
            amount="12.50",
            client_reference="browser-123",
        )
        self.assertEqual(again.pk, contribution.pk)
        obligation = contribution.payment_obligation
        self.assertEqual(obligation.payer_profile, self.contributor)
        self.assertEqual(obligation.payee_profile, self.owner)
        self.assertEqual(obligation.amount, Decimal("12.50"))
        self.assertEqual(obligation.currency, "USD")
        self.assertEqual(obligation.status, PaymentObligationStatus.PENDING)
        self.assertEqual(obligation.source_key, f"funding:{contribution.pk}")

    def test_minimum_maximum_and_window_are_enforced(self):
        self.funding.maximum_contribution = Decimal("20.00")
        self.funding.save()
        with self.assertRaises(ValidationError):
            create_funding_contribution(funding=self.funding, actor=self.contributor, amount="1.00")
        with self.assertRaises(ValidationError):
            create_funding_contribution(funding=self.funding, actor=self.contributor, amount="21.00")

        self.funding.opens_at = timezone.now() + timedelta(days=1)
        self.funding.save()
        with self.assertRaises(ValidationError):
            create_funding_contribution(funding=self.funding, actor=self.contributor, amount="10.00")

    def test_invalid_financing_configuration_is_rejected(self):
        funding = FundingDetails(
            activity=self.funding.activity,
            currency="US",
            minimum_contribution=Decimal("10.00"),
            maximum_contribution=Decimal("5.00"),
        )
        with self.assertRaises(ValidationError):
            funding.full_clean()
