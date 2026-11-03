from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from organizations.models import Organization

from .models import Offer, OfferStatus, PaymentMode
from .offer_price_facts import offer_price_facts, occurrence_variant_price_facts, offer_price_facts_many


class OfferPriceFactsTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="offer-facts-owner", email="offer-facts@example.test",
            password="test-pass-2026",
        )
        self.space = Organization.objects.create(
            name="Offer Facts Space", created_by=self.user,
        )
        self.activity = Activity.objects.create(
            space=self.space, created_by=self.user, title="Example Activity",
        )
        self.occurrence = Occurrence.objects.create(
            activity=self.activity, label="Session A",
            start_at=timezone.now() + timedelta(days=2),
            end_at=timezone.now() + timedelta(days=2, hours=1),
        )
        self.other_occurrence = Occurrence.objects.create(
            activity=self.activity, label="Session B",
            start_at=timezone.now() + timedelta(days=3),
            end_at=timezone.now() + timedelta(days=3, hours=1),
        )
        self.now = timezone.now()

    def make_offer(
        self, price, *, occurrence=None, currency="USD", status=OfferStatus.ACTIVE,
        available_from=None, available_until=None,
    ):
        return Offer.objects.create(
            activity=self.activity, occurrence=occurrence,
            name=f"Offer {price} {currency}",
            unit_price=Decimal(price), currency=currency, status=status,
            payment_mode=(
                PaymentMode.NONE if Decimal(price) == 0 else PaymentMode.UPFRONT
            ),
            available_from=available_from, available_until=available_until,
        )

    def test_batch_owner_facts_match_single_contexts(self):
        self.make_offer("10.00")
        self.make_offer("30.00", occurrence=self.occurrence)
        self.make_offer("70.00", occurrence=self.other_occurrence)
        contexts = (
            (self.activity.pk, None),
            (self.activity.pk, self.occurrence.pk),
            (self.activity.pk, self.other_occurrence.pk),
        )
        with self.assertNumQueries(1):
            batch = offer_price_facts_many(contexts=contexts, at=self.now)
        for activity_id, occurrence_id in contexts:
            single = (
                offer_price_facts(activity=self.activity, at=self.now)
                if occurrence_id is None else
                offer_price_facts(
                    occurrence=self.occurrence if occurrence_id == self.occurrence.pk
                    else self.other_occurrence,
                    at=self.now,
                )
            )
            self.assertEqual(
                batch[(str(activity_id), str(occurrence_id) if occurrence_id else None)].as_dict(),
                single.as_dict(),
            )

    def test_missing_offer_is_unknown_not_free(self):
        result = offer_price_facts(activity=self.activity, at=self.now)
        self.assertEqual(result.as_dict()["state"], "unknown")
        self.assertEqual(result.as_dict()["reason"], "no_applicable_offer")
        self.assertIsNone(result.minimum)

    def test_active_free_offer_is_explicitly_free(self):
        self.make_offer("0.00")
        result = offer_price_facts(activity=self.activity, at=self.now)
        self.assertEqual(result.state, "free")
        self.assertEqual(result.as_dict()["minimum"], "0.00")
        self.assertEqual(result.as_dict()["fact_freshness"], "not_asserted")

    def test_exact_and_range_prices_preserve_currency(self):
        self.make_offer("10.00")
        exact = offer_price_facts(activity=self.activity, at=self.now)
        self.assertEqual(exact.state, "exact")
        self.assertEqual(exact.currency, "USD")
        self.make_offer("30.00")
        ranged = offer_price_facts(activity=self.activity, at=self.now)
        self.assertEqual(ranged.state, "range")
        self.assertEqual((ranged.minimum, ranged.maximum), (
            Decimal("10.00"), Decimal("30.00")
        ))

    def test_mixed_currencies_are_not_compared(self):
        self.make_offer("20.00", currency="USD")
        self.make_offer("1000.00", currency="CDF")
        result = offer_price_facts(activity=self.activity, at=self.now)
        self.assertEqual(result.state, "unknown")
        self.assertEqual(result.reason, "mixed_currencies")
        self.assertIsNone(result.currency)
        self.assertIsNone(result.minimum)

    def test_scope_excludes_other_occurrence_price(self):
        self.make_offer("10.00")
        self.make_offer("30.00", occurrence=self.occurrence)
        self.make_offer("70.00", occurrence=self.other_occurrence)
        activity_facts = offer_price_facts(activity=self.activity, at=self.now)
        occurrence_facts = offer_price_facts(occurrence=self.occurrence, at=self.now)
        self.assertEqual(activity_facts.state, "exact")
        self.assertEqual(activity_facts.minimum, Decimal("10.00"))
        self.assertEqual(occurrence_facts.state, "range")
        self.assertEqual(occurrence_facts.maximum, Decimal("30.00"))

    def test_future_expired_and_inactive_offers_are_not_present_prices(self):
        self.make_offer("10.00", available_from=self.now + timedelta(days=1))
        self.make_offer("20.00", available_until=self.now - timedelta(seconds=1))
        self.make_offer("30.00", status=OfferStatus.INACTIVE)
        result = offer_price_facts(activity=self.activity, at=self.now)
        self.assertEqual(result.state, "unknown")
        self.assertEqual(result.offer_count, 0)

    def test_source_update_and_end_are_not_fact_verification(self):
        end = self.now + timedelta(days=4)
        self.make_offer("10.00", available_until=end)
        facts = offer_price_facts(activity=self.activity, at=self.now).as_dict()
        self.assertIsNotNone(facts["owner_updated_at"])
        self.assertEqual(facts["earliest_offer_end_at"], end.isoformat())
        self.assertEqual(facts["fact_freshness"], "not_asserted")

    def test_context_is_required(self):
        with self.assertRaises(ValueError):
            offer_price_facts()
        with self.assertRaises(ValueError):
            offer_price_facts(activity=self.activity, occurrence=self.occurrence)

    def test_occurrence_variants_show_owner_backed_different_prices(self):
        self.make_offer("10.00", occurrence=self.occurrence)
        self.make_offer("40.00", occurrence=self.other_occurrence)
        result = occurrence_variant_price_facts(
            occurrences=[self.occurrence, self.other_occurrence], at=self.now,
        )
        self.assertEqual(result["state"], "variant_dependent")
        self.assertEqual(result["minimum"], "10.00")
        self.assertEqual(result["maximum"], "40.00")
        self.assertEqual(result["currency"], "USD")
        self.assertEqual(
            {v["occurrence"]["id"] for v in result["variants"]},
            {str(self.occurrence.pk), str(self.other_occurrence.pk)},
        )

    def test_variants_do_not_convert_currencies_or_infer_unknown_price(self):
        self.make_offer("10.00", occurrence=self.occurrence)
        self.make_offer(
            "1000.00", occurrence=self.other_occurrence, currency="CDF",
        )
        result = occurrence_variant_price_facts(
            occurrences=[self.occurrence, self.other_occurrence], at=self.now,
        )
        self.assertEqual(result["state"], "unknown")
        self.assertIsNone(result["currency"])
        self.assertIsNone(result["minimum"])
        self.assertEqual(len(result["variants"]), 2)

    def test_variant_comparison_rejects_unrelated_or_repeated_occurrences(self):
        with self.assertRaises(ValueError):
            occurrence_variant_price_facts(
                occurrences=[self.occurrence, self.occurrence],
            )
