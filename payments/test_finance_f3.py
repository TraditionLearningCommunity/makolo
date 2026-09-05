from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity, Occurrence
from authorization.services import ensure_platform_admin_mandate
from commerce.models import Offer, OfferStatus, PaymentMode
from commerce.pricing import ChargeIncidence, ChargeRule, FinancialComponentType
from commerce.services import create_order
from journeys.models import WorkflowKind
from journeys.services import create_journey
from organizations.models import Organization

from .financial_selectors import financial_position_summary
from .financial_services import (
    build_financial_allocation,
    recognize_payment_financials,
    record_financial_adjustment,
    record_refund_financials,
    validate_financial_allocation,
)
from .models import (
    FinancialAllocationLine,
    FinancialAllocationLineType,
    FundsCustody,
    LedgerEntry,
    LedgerEntryType,
    Payment,
    PaymentMethod,
    PaymentObligationProcessingMode,
    PaymentObligationReason,
    PaymentProvider,
    PaymentStatus,
    Refund,
    RefundStatus,
)
from .obligation_services import create_commerce_payment_obligation, create_payment_obligation
from .services import complete_payment, fail_payment


class FinanceF3Tests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="finance-f3-user",
            email="finance-f3@example.com",
        )
        self.staff = get_user_model().objects.create_user(
            username="finance-f3-staff",
            email="finance-f3-staff@example.com",
            is_staff=True,
        )
        ensure_platform_admin_mandate(profile=self.staff, source="pre-m7-test")
        self.space = Organization.objects.create(name="Finance F3 Space", created_by=self.user)
        self.activity = Activity.objects.create(space=self.space, created_by=self.user, title="Finance F3")
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

    def commerce_order(self, *, charges=()):
        offer = Offer.objects.create(
            activity=self.activity,
            occurrence=self.occurrence,
            name="Billet F3",
            unit_price=Decimal("10.00"),
            currency="USD",
            payment_mode=PaymentMode.UPFRONT,
            status=OfferStatus.ACTIVE,
        )
        return create_order(
            journey=self.journey(),
            buyer=self.user,
            selections=[(offer, 1)],
            payee_space=self.space,
            financial_charges=charges,
        )

    def subscription_obligation(self, amount="20.00", suffix="default"):
        return create_payment_obligation(
            reason=PaymentObligationReason.SUBSCRIPTION,
            label="Abonnement Makolo",
            amount=Decimal(amount),
            currency="USD",
            processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
            payer_profile=self.user,
            payee_platform=True,
            source_key=f"subscription:f3:{suffix}",
        )

    def pending_payment(self, obligation, suffix):
        return Payment.objects.create(
            obligation=obligation,
            initiated_by=self.user,
            provider=PaymentProvider.SANDBOX,
            method=PaymentMethod.CARD,
            status=PaymentStatus.PENDING,
            amount=obligation.amount,
            currency=obligation.currency,
            idempotency_key=f"f3-payment-{suffix}",
        )

    def test_commerce_snapshot_builds_balanced_explicit_allocation(self):
        charges = [
            ChargeRule(code="makolo", label="Makolo", component_type=FinancialComponentType.MAKOLO_FEE, incidence=ChargeIncidence.PAYER, fixed_amount=Decimal("1.00")),
            ChargeRule(code="tax", label="Taxe", component_type=FinancialComponentType.TAX, incidence=ChargeIncidence.PAYER, fixed_amount=Decimal("0.50")),
            ChargeRule(code="processing", label="Traitement", component_type=FinancialComponentType.PROCESSING_FEE, incidence=ChargeIncidence.PAYER, fixed_amount=Decimal("0.50")),
        ]
        order = self.commerce_order(charges=charges)
        obligation = create_commerce_payment_obligation(commerce_order=order, actor=self.user)
        allocation = build_financial_allocation(obligation=obligation)
        amounts = {line.line_type: line.amount for line in allocation.lines.all()}
        self.assertEqual(order.total, Decimal("12.00"))
        self.assertEqual(amounts[FinancialAllocationLineType.PAYEE], Decimal("10.00"))
        self.assertEqual(amounts[FinancialAllocationLineType.PLATFORM], Decimal("1.00"))
        self.assertEqual(amounts[FinancialAllocationLineType.TAX], Decimal("0.50"))
        self.assertEqual(amounts[FinancialAllocationLineType.PROCESSING], Decimal("0.50"))
        self.assertEqual(sum(amounts.values(), Decimal("0.00")), obligation.amount)
        self.assertEqual(allocation.source_snapshot, order.financial_snapshot)

    def test_legacy_commerce_does_not_invent_commission_and_snapshot_is_historical(self):
        order = self.commerce_order(charges=())
        original_snapshot = order.financial_snapshot.copy()
        obligation = create_commerce_payment_obligation(commerce_order=order, actor=self.user)
        allocation = build_financial_allocation(obligation=obligation)
        lines = list(allocation.lines.all())
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0].line_type, FinancialAllocationLineType.PAYEE)
        self.assertEqual(lines[0].amount, Decimal("10.00"))
        future_rule = ChargeRule(code="future", label="Future", component_type=FinancialComponentType.MAKOLO_FEE, incidence=ChargeIncidence.PAYER, fixed_amount=Decimal("9.00"))
        self.assertEqual(future_rule.fixed_amount, Decimal("9.00"))
        self.assertEqual(build_financial_allocation(obligation=obligation).source_snapshot, original_snapshot)

    def test_subscription_allocation_is_platform_only_without_journey(self):
        obligation = self.subscription_obligation()
        allocation = build_financial_allocation(obligation=obligation)
        line = allocation.lines.get()
        self.assertIsNone(obligation.journey_id)
        self.assertIsNone(obligation.commerce_order_id)
        self.assertEqual(line.line_type, FinancialAllocationLineType.PLATFORM)
        self.assertTrue(line.beneficiary_platform)
        self.assertFalse(allocation.lines.filter(line_type=FinancialAllocationLineType.PAYEE).exists())

    def test_pending_and_failed_payment_do_not_recognize_revenue(self):
        pending_obligation = self.subscription_obligation(suffix="pending")
        pending = self.pending_payment(pending_obligation, "pending")
        self.assertFalse(LedgerEntry.objects.filter(payment=pending).exists())

        failed_obligation = self.subscription_obligation(suffix="failed")
        failed = self.pending_payment(failed_obligation, "failed")
        fail_payment(payment=failed, failure_code="declined")
        self.assertFalse(LedgerEntry.objects.filter(payment=failed).exists())

    def test_success_is_atomic_idempotent_and_distinguishes_gmv_from_platform_amount(self):
        obligation = self.subscription_obligation(suffix="success")
        payment = self.pending_payment(obligation, "success")
        complete_payment(payment=payment, provider_reference="f3-success-1")
        summary = financial_position_summary(obligation=obligation)
        self.assertEqual(summary["gmv"], Decimal("20.00"))
        self.assertEqual(summary["platform_amount"], Decimal("20.00"))
        self.assertEqual(summary["payee_payable"], Decimal("0.00"))
        count = LedgerEntry.objects.filter(payment=payment).count()
        complete_payment(payment=payment, provider_reference="f3-success-1")
        recognize_payment_financials(payment=payment)
        self.assertEqual(LedgerEntry.objects.filter(payment=payment).count(), count)

        order = self.commerce_order(charges=[ChargeRule(code="makolo-10", label="Makolo", component_type=FinancialComponentType.MAKOLO_FEE, incidence=ChargeIncidence.PAYER, fixed_amount=Decimal("1.00"))])
        commerce_obligation = create_commerce_payment_obligation(commerce_order=order, actor=self.user)
        commerce_payment = self.pending_payment(commerce_obligation, "gmv")
        commerce_payment.commerce_order = order
        commerce_payment.save(update_fields=["commerce_order", "updated_at"])
        complete_payment(payment=commerce_payment, provider_reference="f3-success-gmv")
        commerce_summary = financial_position_summary(obligation=commerce_obligation)
        self.assertEqual(commerce_summary["gmv"], Decimal("11.00"))
        self.assertEqual(commerce_summary["platform_amount"], Decimal("1.00"))
        self.assertEqual(commerce_summary["payee_payable"], Decimal("10.00"))

    def test_currency_mismatch_is_refused_by_financial_recognition(self):
        obligation = self.subscription_obligation(suffix="currency")
        payment = Payment(
            reference="PAY-F3MISMATCH",
            obligation=obligation,
            provider=PaymentProvider.SANDBOX,
            method=PaymentMethod.CARD,
            status=PaymentStatus.SUCCEEDED,
            amount=obligation.amount,
            currency="EUR",
        )
        Payment.objects.bulk_create([payment])
        with self.assertRaises(ValidationError):
            recognize_payment_financials(payment=payment)

    def test_ledger_is_append_only_and_adjustment_is_compensating_entry(self):
        obligation = self.subscription_obligation(suffix="append")
        payment = self.pending_payment(obligation, "append")
        complete_payment(payment=payment, provider_reference="f3-append")
        original = LedgerEntry.objects.filter(payment=payment, entry_type=LedgerEntryType.PLATFORM_REVENUE).get()
        original.amount = Decimal("99.00")
        with self.assertRaises(ValidationError):
            original.save()
        with self.assertRaises(ValidationError):
            LedgerEntry.objects.filter(pk=original.pk).update(amount=Decimal("99.00"))
        with self.assertRaises(PermissionDenied):
            record_financial_adjustment(obligation=obligation, economic_role=FinancialAllocationLineType.PLATFORM, amount=Decimal("-1.00"), currency="USD", reason="Correction", idempotency_key="no-staff", actor=self.user)
        adjustment = record_financial_adjustment(obligation=obligation, economic_role=FinancialAllocationLineType.PLATFORM, amount=Decimal("-1.00"), currency="USD", reason="Correction auditée", idempotency_key="platform-1", actor=self.staff)
        self.assertEqual(adjustment.entry_type, LedgerEntryType.ADJUSTMENT)
        original.refresh_from_db()
        self.assertEqual(original.amount, Decimal("20.00"))
        self.assertEqual(financial_position_summary(obligation=obligation)["platform_amount"], Decimal("19.00"))

    def test_unbalanced_allocation_is_rejected(self):
        obligation = self.subscription_obligation(suffix="unbalanced")
        allocation = build_financial_allocation(obligation=obligation)
        line = allocation.lines.get()
        FinancialAllocationLine.objects.create(
            allocation=allocation,
            sequence=2,
            line_type=FinancialAllocationLineType.OTHER,
            amount=Decimal("1.00"),
            currency="USD",
            source_component_type="test",
        )
        with self.assertRaises(ValidationError):
            validate_financial_allocation(allocation)
        self.assertEqual(line.amount, Decimal("20.00"))

    def test_full_and_partial_refunds_create_idempotent_reversals(self):
        full_obligation = self.subscription_obligation(amount="12.00", suffix="refund-full")
        full_payment = self.pending_payment(full_obligation, "refund-full")
        complete_payment(payment=full_payment, provider_reference="f3-refund-full")
        refund = Refund.objects.create(
            payment=full_payment,
            requested_by=self.staff,
            status=RefundStatus.SUCCEEDED,
            amount=Decimal("12.00"),
            currency="USD",
            provider_reference="refund-full",
            processed_at=timezone.now(),
        )
        full_summary = financial_position_summary(obligation=full_obligation)
        self.assertEqual(full_summary["refund_total"], Decimal("12.00"))
        self.assertEqual(full_summary["platform_amount"], Decimal("0.00"))
        reversal_count = LedgerEntry.objects.filter(refund=refund).count()
        record_refund_financials(refund=refund)
        self.assertEqual(LedgerEntry.objects.filter(refund=refund).count(), reversal_count)

        partial_obligation = self.subscription_obligation(amount="20.00", suffix="refund-partial")
        partial_payment = self.pending_payment(partial_obligation, "refund-partial")
        complete_payment(payment=partial_payment, provider_reference="f3-refund-partial")
        line = partial_obligation.financial_allocation.lines.get()
        Refund.objects.create(
            payment=partial_payment,
            requested_by=self.staff,
            status=RefundStatus.SUCCEEDED,
            amount=Decimal("5.00"),
            currency="USD",
            provider_reference="refund-partial",
            processed_at=timezone.now(),
            financial_breakdown=[{"allocation_line_id": str(line.pk), "amount": "5.00"}],
        )
        partial_summary = financial_position_summary(obligation=partial_obligation)
        self.assertEqual(partial_summary["refund_total"], Decimal("5.00"))
        self.assertEqual(partial_summary["platform_amount"], Decimal("15.00"))

    def test_external_custody_is_not_projected_as_makolo_payee_payable(self):
        obligation = create_payment_obligation(
            journey=self.journey(),
            reason=PaymentObligationReason.OTHER,
            label="Paiement externe",
            amount=Decimal("10.00"),
            currency="USD",
            processing_mode=PaymentObligationProcessingMode.EXTERNAL,
            payer_profile=self.user,
            payee_space=self.space,
            source_key="f3:external:allocation",
        )
        allocation = build_financial_allocation(obligation=obligation)
        line = allocation.lines.get()
        LedgerEntry.objects.create(
            obligation=obligation,
            allocation=allocation,
            allocation_line=line,
            entry_type=LedgerEntryType.PAYEE_PAYABLE,
            economic_role=FinancialAllocationLineType.PAYEE,
            amount=Decimal("10.00"),
            currency="USD",
            source_kind="payment_evidence",
            source_key="f3:external:ledger",
            funds_custody=FundsCustody.EXTERNAL,
        )
        summary = financial_position_summary(obligation=obligation)
        self.assertEqual(summary["payee_payable"], Decimal("0.00"))
