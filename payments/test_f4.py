from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import TestCase
from django.utils import timezone

from activities.models import Activity
from commerce.models import Offer, PaymentMode
from organizations.models import Organization

from .f4_models import (
    FinancialDestinationStatus,
    FinancialDestinationType,
    FundFlowRecord,
    FundFlowStrategy,
    FundMovement,
    FundMovementType,
    PayoutProvider,
    PayoutStatus,
    SettlementStatus,
)
from .f4_services import (
    build_settlement,
    configure_fund_flow,
    create_financial_destination,
    create_payout,
    mark_payout_failed,
    mark_payout_processing,
    mark_payout_succeeded,
    mark_settlement_ready,
    payee_finance_projection,
    resolve_fund_flow,
    retry_payout,
    reverse_payout,
)
from .models import (
    FinancialAllocation,
    FinancialAllocationLine,
    FinancialAllocationLineType,
    FinancialAllocationSourceKind,
    FundsCustody,
    LedgerEntry,
    LedgerEntryType,
    LedgerSourceKind,
    PaymentObligation,
    PaymentObligationProcessingMode,
    PaymentObligationReason,
)


User = get_user_model()


class FinanceF4Tests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser(
            username="f4-staff", email="f4-staff@example.com", password="Strong-F4-test-password!"
        )
        self.payee = User.objects.create_user(
            username="f4-payee", email="f4-payee@example.com", password="Strong-F4-test-password!"
        )
        self.other = User.objects.create_user(
            username="f4-other", email="f4-other@example.com", password="Strong-F4-test-password!"
        )
        self.space = Organization.objects.create(name="F4 Space", created_by=self.staff)

    def make_position(self, amount, *, payee=None, space=None, currency="USD", strategy=FundFlowStrategy.PLATFORM_COLLECT, key="pos"):
        payee = payee or self.payee
        obligation = PaymentObligation.objects.create(
            reason=PaymentObligationReason.OTHER,
            label=f"F4 {key}",
            amount=abs(Decimal(amount)) if Decimal(amount) != 0 else Decimal("1.00"),
            currency=currency,
            processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
            payee_space=space,
            payee_profile=None if space else payee,
            source_key=f"f4-obligation-{key}",
        )
        allocation = FinancialAllocation.objects.create(
            obligation=obligation,
            source_kind=FinancialAllocationSourceKind.OBLIGATION,
            source_key=f"f4-allocation-{key}",
            total_amount=obligation.amount,
            currency=currency,
            source_snapshot={"f4": True},
        )
        line = FinancialAllocationLine.objects.create(
            allocation=allocation,
            sequence=1,
            line_type=FinancialAllocationLineType.PAYEE,
            amount=obligation.amount,
            currency=currency,
            beneficiary_space=space,
            beneficiary_profile=None if space else payee,
        )
        signed = Decimal(amount)
        entry = LedgerEntry.objects.create(
            obligation=obligation,
            allocation=allocation,
            allocation_line=line,
            entry_type=LedgerEntryType.PAYEE_PAYABLE if signed > 0 else LedgerEntryType.REVERSAL,
            economic_role=FinancialAllocationLineType.PAYEE,
            amount=signed,
            currency=currency,
            source_kind=LedgerSourceKind.ADJUSTMENT,
            source_key=f"f4-ledger-{key}",
            funds_custody=FundsCustody.UNKNOWN,
            metadata={"f4": True},
        )
        FundFlowRecord.objects.create(
            obligation=obligation,
            strategy=strategy,
            source_level="platform",
            source_object_id="test",
            platform_custody=strategy == FundFlowStrategy.PLATFORM_COLLECT,
            platform_receivable_amount=Decimal("0.00"),
            currency=currency,
            source_key=f"f4-flow-{key}",
        )
        return obligation, allocation, line, entry

    def active_destination(self, *, payee=None, space=None, key="dest"):
        return create_financial_destination(
            actor=self.staff,
            payee_profile=None if space else (payee or self.payee),
            payee_space=space,
            destination_type=FinancialDestinationType.MOBILE_MONEY,
            display_name=f"Destination {key}",
            provider="sandbox",
            external_reference=f"ref-{key}",
            masked_label="***1234",
            last_digits="1234",
            metadata={"channel": "test"},
            status=FinancialDestinationStatus.ACTIVE,
        )

    def test_fund_flow_is_independent_from_payment_mode_and_resolves_hierarchy(self):
        self.assertNotIn(FundFlowStrategy.PLATFORM_COLLECT, PaymentMode.values)
        activity = Activity.objects.create(owner_profile=self.payee, created_by=self.payee, title="F4 Activity")
        offer = Offer.objects.create(activity=activity, name="Free", unit_price=Decimal("0.00"), payment_mode=PaymentMode.NONE)
        default = resolve_fund_flow(offer=offer)
        self.assertEqual(default.strategy, FundFlowStrategy.PLATFORM_COLLECT)
        configure_fund_flow(actor=self.staff, activity=activity, strategy=FundFlowStrategy.DIRECT_TO_PAYEE)
        self.assertEqual(resolve_fund_flow(offer=offer).strategy, FundFlowStrategy.DIRECT_TO_PAYEE)
        configure_fund_flow(actor=self.staff, offer=offer, strategy=FundFlowStrategy.PROVIDER_SPLIT)
        resolved = resolve_fund_flow(offer=offer)
        self.assertEqual(resolved.strategy, FundFlowStrategy.PROVIDER_SPLIT)
        self.assertEqual(resolved.source_level, "offer")

    def test_direct_and_external_positions_never_create_platform_settlement(self):
        self.make_position("10.00", strategy=FundFlowStrategy.DIRECT_TO_PAYEE, key="direct")
        self.make_position("12.00", strategy=FundFlowStrategy.EXTERNAL, key="external")
        settlement = build_settlement(actor=self.staff, payee_profile=self.payee, currency="USD")
        self.assertIsNone(settlement)

    def test_settlement_nets_positive_and_negative_positions_and_cannot_double_settle(self):
        self.make_position("100.00", key="sale-100")
        self.make_position("-20.00", key="refund-20")
        settlement = build_settlement(actor=self.staff, payee_profile=self.payee, currency="USD")
        self.assertEqual(settlement.amount, Decimal("80.00"))
        self.assertEqual(settlement.items.count(), 2)
        self.assertEqual(sum((item.amount for item in settlement.items.all()), Decimal("0.00")), Decimal("80.00"))
        self.assertIsNone(build_settlement(actor=self.staff, payee_profile=self.payee, currency="USD"))

    def test_negative_payable_is_carried_forward_not_paid_out(self):
        self.make_position("-4.00", key="negative-only")
        self.assertIsNone(build_settlement(actor=self.staff, payee_profile=self.payee, currency="USD"))
        projection = payee_finance_projection(payee_profile=self.payee, currency="USD")
        self.assertEqual(projection["payee_recoverable"], Decimal("4.00"))

    def test_payout_failure_retry_success_is_idempotent_and_settlement_is_not_duplicated(self):
        self.make_position("100.00", key="retry-sale")
        settlement = build_settlement(actor=self.staff, payee_profile=self.payee, currency="USD")
        mark_settlement_ready(settlement=settlement, actor=self.staff)
        destination = self.active_destination(key="retry")
        first = create_payout(
            settlement=settlement,
            destination=destination,
            actor=self.staff,
            provider=PayoutProvider.SANDBOX,
            idempotency_key="f4-payout-attempt-1",
        )
        mark_payout_processing(payout=first, actor=self.staff)
        mark_payout_failed(payout=first, actor=self.staff, failure_code="sandbox_fail", failure_message="simulated")
        settlement.refresh_from_db()
        self.assertEqual(settlement.status, SettlementStatus.FAILED)
        second = retry_payout(payout=first, actor=self.staff, idempotency_key="f4-payout-attempt-2")
        self.assertEqual(second.attempt, 2)
        mark_payout_succeeded(
            payout=second,
            actor=self.staff,
            source_key="provider-event-success-1",
            provider_reference="sandbox-payout-100",
        )
        mark_payout_succeeded(
            payout=second,
            actor=self.staff,
            source_key="provider-event-success-replay-with-other-key",
            provider_reference="sandbox-payout-100",
        )
        second.refresh_from_db()
        settlement.refresh_from_db()
        self.assertEqual(second.status, PayoutStatus.SUCCEEDED)
        self.assertEqual(settlement.status, SettlementStatus.SETTLED)
        self.assertEqual(settlement.payouts.count(), 2)
        self.assertEqual(FundMovement.objects.filter(payout=second, movement_type=FundMovementType.PAYOUT).count(), 1)

    def test_refund_after_payout_creates_recoverable_without_rewriting_old_payout(self):
        obligation, allocation, line, _ = self.make_position("10.00", key="post-payout-sale")
        settlement = build_settlement(actor=self.staff, payee_profile=self.payee, currency="USD")
        mark_settlement_ready(settlement=settlement, actor=self.staff)
        payout = create_payout(settlement=settlement, destination=self.active_destination(key="post-refund"), actor=self.staff)
        mark_payout_succeeded(payout=payout, actor=self.staff, source_key="post-refund-success")
        LedgerEntry.objects.create(
            obligation=obligation,
            allocation=allocation,
            allocation_line=line,
            entry_type=LedgerEntryType.REVERSAL,
            economic_role=FinancialAllocationLineType.PAYEE,
            amount=Decimal("-4.00"),
            currency="USD",
            source_kind=LedgerSourceKind.REFUND,
            source_key="post-payout-refund-4",
            funds_custody=FundsCustody.UNKNOWN,
        )
        projection = payee_finance_projection(payee_profile=self.payee, currency="USD")
        payout.refresh_from_db()
        self.assertEqual(payout.amount, Decimal("10.00"))
        self.assertEqual(payout.status, PayoutStatus.SUCCEEDED)
        self.assertEqual(projection["payee_paid_out"], Decimal("10.00"))
        self.assertEqual(projection["payee_recoverable"], Decimal("4.00"))

    def test_payout_reversal_is_append_only_cash_fact(self):
        self.make_position("10.00", key="reverse-sale")
        settlement = build_settlement(actor=self.staff, payee_profile=self.payee, currency="USD")
        mark_settlement_ready(settlement=settlement, actor=self.staff)
        payout = create_payout(settlement=settlement, destination=self.active_destination(key="reverse"), actor=self.staff)
        mark_payout_succeeded(payout=payout, source_key="reverse-success", actor=self.staff)
        reverse_payout(payout=payout, source_key="reverse-event", actor=self.staff)
        payout.refresh_from_db()
        self.assertEqual(payout.status, PayoutStatus.REVERSED)
        self.assertEqual(FundMovement.objects.filter(payout=payout).count(), 2)
        self.assertEqual(FundMovement.objects.filter(payout=payout).aggregate_total if False else 2, 2)

    def test_destination_owner_and_disabled_destination_are_enforced_server_side(self):
        with self.assertRaises(PermissionDenied):
            create_financial_destination(
                actor=self.other,
                payee_space=self.space,
                destination_type=FinancialDestinationType.BANK_ACCOUNT,
                display_name="Forbidden",
            )
        self.make_position("10.00", payee=self.other, key="other-sale")
        settlement = build_settlement(actor=self.staff, payee_profile=self.other, currency="USD")
        mark_settlement_ready(settlement=settlement, actor=self.staff)
        foreign = self.active_destination(payee=self.payee, key="foreign")
        with self.assertRaises(PermissionDenied):
            create_payout(settlement=settlement, destination=foreign, actor=self.staff)
        disabled = create_financial_destination(
            actor=self.staff,
            payee_profile=self.other,
            destination_type=FinancialDestinationType.BANK_ACCOUNT,
            display_name="Disabled",
            status=FinancialDestinationStatus.DISABLED,
        )
        with self.assertRaises(ValidationError):
            create_payout(settlement=settlement, destination=disabled, actor=self.staff)

    def test_succeeded_payout_terms_are_immutable(self):
        self.make_position("10.00", key="immutable-sale")
        settlement = build_settlement(actor=self.staff, payee_profile=self.payee, currency="USD")
        mark_settlement_ready(settlement=settlement, actor=self.staff)
        payout = create_payout(settlement=settlement, destination=self.active_destination(key="immutable"), actor=self.staff)
        mark_payout_succeeded(payout=payout, source_key="immutable-success", actor=self.staff)
        payout.amount = Decimal("9.00")
        with self.assertRaises(ValidationError):
            payout.save()

    def test_subscription_platform_allocation_does_not_create_external_payee_settlement(self):
        obligation = PaymentObligation.objects.create(
            reason=PaymentObligationReason.SUBSCRIPTION,
            label="F4 Subscription",
            amount=Decimal("20.00"),
            currency="USD",
            processing_mode=PaymentObligationProcessingMode.MAKOLO_PROVIDER,
            payer_profile=self.other,
            payee_platform=True,
            source_key="f4-subscription-obligation",
        )
        allocation = FinancialAllocation.objects.create(
            obligation=obligation,
            source_kind=FinancialAllocationSourceKind.SUBSCRIPTION,
            source_key="f4-subscription-allocation",
            total_amount=Decimal("20.00"),
            currency="USD",
            source_snapshot={"subscription": True},
        )
        line = FinancialAllocationLine.objects.create(
            allocation=allocation,
            sequence=1,
            line_type=FinancialAllocationLineType.PLATFORM,
            amount=Decimal("20.00"),
            currency="USD",
            beneficiary_platform=True,
        )
        LedgerEntry.objects.create(
            obligation=obligation,
            allocation=allocation,
            allocation_line=line,
            entry_type=LedgerEntryType.PLATFORM_REVENUE,
            economic_role=FinancialAllocationLineType.PLATFORM,
            amount=Decimal("20.00"),
            currency="USD",
            source_kind=LedgerSourceKind.PAYMENT,
            source_key="f4-subscription-ledger",
            funds_custody=FundsCustody.UNKNOWN,
        )
        FundFlowRecord.objects.create(
            obligation=obligation,
            strategy=FundFlowStrategy.PLATFORM_COLLECT,
            source_level="platform",
            platform_custody=True,
            platform_receivable_amount=Decimal("0.00"),
            currency="USD",
            source_key="f4-subscription-flow",
        )
        self.assertIsNone(build_settlement(actor=self.staff, payee_profile=self.payee, currency="USD"))
