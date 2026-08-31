from decimal import Decimal

from django.db.models import Sum

from .models import (
    FinancialAllocationLineType,
    FundsCustody,
    LedgerEntry,
    LedgerEntryType,
)


ZERO = Decimal("0.00")


def ledger_entries(*, obligation=None, start_at=None, end_at=None):
    queryset = LedgerEntry.objects.select_related("allocation", "allocation_line", "obligation")
    if obligation is not None:
        queryset = queryset.filter(obligation=obligation)
    if start_at is not None:
        queryset = queryset.filter(occurred_at__gte=start_at)
    if end_at is not None:
        queryset = queryset.filter(occurred_at__lt=end_at)
    return queryset


def _sum(queryset):
    return queryset.aggregate(total=Sum("amount"))["total"] or ZERO


def financial_position_summary(*, obligation=None, start_at=None, end_at=None):
    entries = ledger_entries(obligation=obligation, start_at=start_at, end_at=end_at)
    gmv = _sum(entries.filter(entry_type=LedgerEntryType.PAYMENT_RECOGNIZED))
    refund_signed = _sum(entries.filter(entry_type=LedgerEntryType.REFUND))
    payee_payable = _sum(
        entries.filter(economic_role=FinancialAllocationLineType.PAYEE).exclude(
            funds_custody=FundsCustody.EXTERNAL
        )
    )
    platform_amount = _sum(entries.filter(economic_role=FinancialAllocationLineType.PLATFORM))
    tax_liability = _sum(entries.filter(economic_role=FinancialAllocationLineType.TAX))
    processing_amount = _sum(entries.filter(economic_role=FinancialAllocationLineType.PROCESSING))
    return {
        "gmv": gmv,
        "platform_amount": platform_amount,
        "payee_payable": payee_payable,
        "tax_liability": tax_liability,
        "processing_amount": processing_amount,
        "refund_total": -refund_signed,
        "net_transaction_amount": gmv + refund_signed,
    }
