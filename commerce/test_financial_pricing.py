from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from journeys.models import WorkflowKind
from journeys.services import create_journey
from organizations.models import Organization

from .models import Offer, OfferStatus, PaymentMode, PricingPolicy
from .pricing import (
    ChargeIncidence,
    ChargeRule,
    FinancialComponentType,
    calculate_quote,
)
from .services import create_order, quote_financials


class FinancialQuoteTests(SimpleTestCase):
    def rule(
        self,
        *,
        fixed="0.00",
        rate="0",
        incidence=ChargeIncidence.PAYER,
        component=FinancialComponentType.OTHER_FEE,
        label="Frais",
    ):
        return ChargeRule(
            code="fee",
            label=label,
            component_type=component,
            incidence=incidence,
            fixed_amount=Decimal(fixed),
            percentage_rate=Decimal(rate),
        )

    def test_price_without_charge(self):
        quote = calculate_quote(currency="USD", subtotal=Decimal("10.00"))
        self.assertEqual(quote.payer_total, Decimal("10.00"))
        self.assertEqual(quote.expected_payee_amount, Decimal("10.00"))
        self.assertEqual(quote.lines, ())

    def test_fixed_fee_supported_by_payer_preserves_seller_net(self):
        quote = calculate_quote(
            currency="USD",
            subtotal=Decimal("10.00"),
            charges=[self.rule(fixed="2.00")],
        )
        self.assertEqual(quote.payer_total, Decimal("12.00"))
        self.assertEqual(quote.expected_payee_amount, Decimal("10.00"))

    def test_percentage_supported_by_payer(self):
        quote = calculate_quote(
            currency="USD",
            subtotal=Decimal("10.00"),
            charges=[self.rule(rate="0.05")],
        )
        self.assertEqual(quote.lines[0].amount, Decimal("0.50"))
        self.assertEqual(quote.payer_total, Decimal("10.50"))

    def test_fixed_plus_percentage_is_deterministic(self):
        charge = self.rule(fixed="0.20", rate="0.05")
        first = calculate_quote(currency="USD", subtotal=Decimal("10.00"), charges=[charge])
        second = calculate_quote(currency="USD", subtotal=Decimal("10.00"), charges=[charge])
        self.assertEqual(first.lines[0].amount, Decimal("0.70"))
        self.assertEqual(first.as_snapshot(), second.as_snapshot())

    def test_customer_total_fixed_deducts_payee_charge_inside_envelope(self):
        quote = calculate_quote(
            currency="USD",
            subtotal=Decimal("12.00"),
            pricing_policy=PricingPolicy.CUSTOMER_TOTAL_FIXED,
            charges=[self.rule(fixed="1.70", incidence=ChargeIncidence.PAYEE)],
        )
        self.assertEqual(quote.payer_total, Decimal("12.00"))
        self.assertEqual(quote.expected_payee_amount, Decimal("10.30"))

    def test_generic_tax_keeps_tax_metadata(self):
        quote = calculate_quote(
            currency="USD",
            subtotal=Decimal("10.00"),
            charges=[
                self.rule(
                    rate="0.05",
                    component=FinancialComponentType.TAX,
                    label="Taxe locale",
                )
            ],
        )
        line = quote.lines[0]
        self.assertEqual(line.component_type, FinancialComponentType.TAX)
        self.assertEqual(line.calculation_base, Decimal("10.00"))
        self.assertEqual(line.percentage_rate, Decimal("0.05"))
        self.assertEqual(line.amount, Decimal("0.50"))

    def test_quantity_base_and_cent_rounding(self):
        quote = calculate_quote(
            currency="USD",
            subtotal=Decimal("29.97"),
            charges=[self.rule(rate="0.025")],
        )
        self.assertEqual(quote.lines[0].amount, Decimal("0.75"))
        self.assertEqual(quote.payer_total, Decimal("30.72"))

    def test_multiple_components_reconstruct_payer_total(self):
        quote = calculate_quote(
            currency="USD",
            subtotal=Decimal("10.00"),
            charges=[
                self.rule(fixed="1.00", component=FinancialComponentType.MAKOLO_FEE),
                ChargeRule(
                    code="processing",
                    label="Traitement",
                    component_type=FinancialComponentType.PROCESSING_FEE,
                    incidence=ChargeIncidence.PAYER,
                    fixed_amount=Decimal("0.50"),
                ),
                ChargeRule(
                    code="tax",
                    label="Taxe",
                    component_type=FinancialComponentType.TAX,
                    incidence=ChargeIncidence.PAYER,
                    fixed_amount=Decimal("0.50"),
                ),
            ],
        )
        self.assertEqual(quote.payer_total, Decimal("12.00"))
        self.assertEqual(sum((line.amount for line in quote.lines), Decimal("0.00")), Decimal("2.00"))
        self.assertEqual(quote.makolo_amount, Decimal("1.00"))

    def test_incoherent_incidence_policy_is_rejected(self):
        with self.assertRaises(ValidationError):
            calculate_quote(
                currency="USD",
                subtotal=Decimal("10.00"),
                pricing_policy=PricingPolicy.SELLER_NET_GUARANTEED,
                charges=[self.rule(fixed="1.00", incidence=ChargeIncidence.PAYEE)],
            )
        with self.assertRaises(ValidationError):
            calculate_quote(
                currency="USD",
                subtotal=Decimal("10.00"),
                pricing_policy=PricingPolicy.CUSTOMER_TOTAL_FIXED,
                charges=[self.rule(fixed="1.00", incidence=ChargeIncidence.PAYER)],
            )

    def test_float_and_negative_inputs_are_rejected(self):
        with self.assertRaises(ValidationError):
            calculate_quote(currency="USD", subtotal=10.0)
        with self.assertRaises(ValidationError):
            calculate_quote(currency="USD", subtotal=Decimal("-1.00"))


class FinancialSnapshotCommerceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="finance-f1-user",
            email="finance-f1@example.com",
            password="test-pass-2026",
        )
        self.space = Organization.objects.create(name="Finance F1 Space", created_by=self.user)
        self.activity = Activity.objects.create(space=self.space, created_by=self.user, title="Finance F1")
        self.occurrence = Occurrence.objects.create(
            activity=self.activity,
            label="Session",
            start_at=timezone.now() + timedelta(days=1),
            end_at=timezone.now() + timedelta(days=1, hours=1),
        )

    def journey(self):
        return create_journey(
            initiated_by=self.user,
            beneficiary=self.user,
            activity=self.activity,
            occurrence=self.occurrence,
            workflow=WorkflowKind.PURCHASE,
        )

    def offer(self, price="10.00"):
        return Offer.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            name="Billet",
            unit_price=Decimal(price),
            currency="USD",
            payment_mode=PaymentMode.UPFRONT,
            status=OfferStatus.ACTIVE,
        )

    def test_quote_and_order_snapshot_are_coherent_for_quantity(self):
        offer = self.offer("9.99")
        charge = ChargeRule(
            code="makolo",
            label="Frais Makolo",
            component_type=FinancialComponentType.MAKOLO_FEE,
            incidence=ChargeIncidence.PAYER,
            fixed_amount=Decimal("0.20"),
            percentage_rate=Decimal("0.05"),
            source="test_policy_v1",
        )
        expected = quote_financials(
            currency="USD",
            subtotal=Decimal("29.97"),
            charges=[charge],
        )
        order = create_order(
            journey=self.journey(),
            buyer=self.user,
            selections=[(offer, 3)],
            payee_space=self.space,
            financial_charges=[charge],
        )
        self.assertEqual(order.total, expected.payer_total)
        self.assertEqual(order.expected_payee_amount, expected.expected_payee_amount)
        self.assertEqual(order.financial_snapshot, expected.as_snapshot())
        self.assertEqual(order.items.get().line_subtotal, Decimal("29.97"))

    def test_customer_total_fixed_snapshot(self):
        offer = self.offer("12.00")
        payee_fee = ChargeRule(
            code="seller-cost",
            label="Charge organisateur",
            component_type=FinancialComponentType.PROCESSING_FEE,
            incidence=ChargeIncidence.PAYEE,
            fixed_amount=Decimal("1.70"),
        )
        order = create_order(
            journey=self.journey(),
            buyer=self.user,
            selections=[(offer, 1)],
            payee_space=self.space,
            pricing_policy=PricingPolicy.CUSTOMER_TOTAL_FIXED,
            financial_charges=[payee_fee],
        )
        self.assertEqual(order.total, Decimal("12.00"))
        self.assertEqual(order.expected_payee_amount, Decimal("10.30"))
        self.assertEqual(order.financial_snapshot["payer_total"], "12.00")
        self.assertEqual(order.financial_snapshot["expected_payee_amount"], "10.30")

    def test_historical_snapshot_is_immutable_when_policy_changes(self):
        offer = self.offer("10.00")
        old_rule = ChargeRule(
            code="makolo",
            label="Frais Makolo",
            component_type=FinancialComponentType.MAKOLO_FEE,
            incidence=ChargeIncidence.PAYER,
            percentage_rate=Decimal("0.05"),
        )
        old_order = create_order(
            journey=self.journey(),
            buyer=self.user,
            selections=[(offer, 1)],
            payee_space=self.space,
            financial_charges=[old_rule],
        )
        old_snapshot = dict(old_order.financial_snapshot)

        new_rule = ChargeRule(
            code="makolo",
            label="Frais Makolo",
            component_type=FinancialComponentType.MAKOLO_FEE,
            incidence=ChargeIncidence.PAYER,
            percentage_rate=Decimal("0.07"),
        )
        new_order = create_order(
            journey=self.journey(),
            buyer=self.user,
            selections=[(offer, 1)],
            payee_space=self.space,
            financial_charges=[new_rule],
        )
        old_order.refresh_from_db()
        self.assertEqual(old_order.financial_snapshot, old_snapshot)
        self.assertEqual(old_order.total, Decimal("10.50"))
        self.assertEqual(new_order.total, Decimal("10.70"))

        old_order.financial_snapshot = {**old_snapshot, "payer_total": "99.00"}
        with self.assertRaises(ValidationError):
            old_order.save()
