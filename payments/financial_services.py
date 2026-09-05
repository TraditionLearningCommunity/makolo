from __future__ import annotations

from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from authorization.services import has_platform_authority
from commerce.pricing import ChargeIncidence, FinancialComponentType, money

from .models import (
    FinancialAllocation,
    FinancialAllocationLine,
    FinancialAllocationLineType,
    FinancialAllocationSourceKind,
    FundsCustody,
    LedgerEntry,
    LedgerEntryType,
    LedgerSourceKind,
    Payment,
    PaymentEvidence,
    PaymentEvidenceStatus,
    PaymentObligation,
    PaymentObligationReason,
    PaymentStatus,
    Refund,
    RefundStatus,
)


ZERO = Decimal("0.00")


def _decimal_money(value, *, label):
    try:
        return money(Decimal(str(value)))
    except Exception as exc:
        raise ValidationError(f"Montant invalide dans le snapshot financier: {label}.") from exc


def _payee_party(obligation):
    return {
        "beneficiary_space": obligation.payee_space,
        "beneficiary_profile": obligation.payee_profile,
        "beneficiary_platform": False,
        "external_beneficiary_name": obligation.external_payee_name,
    }


def _platform_party():
    return {
        "beneficiary_space": None,
        "beneficiary_profile": None,
        "beneficiary_platform": True,
        "external_beneficiary_name": "",
    }


def _empty_party():
    return {
        "beneficiary_space": None,
        "beneficiary_profile": None,
        "beneficiary_platform": False,
        "external_beneficiary_name": "",
    }


def _commerce_specs(obligation):
    order = obligation.commerce_order
    snapshot = order.financial_snapshot or {}
    snapshot_currency = (snapshot.get("currency") or "").upper()
    if snapshot_currency != obligation.currency:
        raise ValidationError("Le snapshot Commerce et l’obligation n’utilisent pas la même devise.")
    payer_total = _decimal_money(snapshot.get("payer_total"), label="payer_total")
    expected_payee = _decimal_money(snapshot.get("expected_payee_amount"), label="expected_payee_amount")
    if payer_total != obligation.amount:
        raise ValidationError("Le payer_total historique ne correspond pas à l’obligation Commerce.")

    specs = []
    if expected_payee > ZERO:
        specs.append(
            {
                "line_type": FinancialAllocationLineType.PAYEE,
                "amount": expected_payee,
                "source_component_type": FinancialComponentType.BASE_PRICE.value,
                "source_component_code": "expected_payee_amount",
                "source_component_index": None,
                "source_metadata": {"snapshot_field": "expected_payee_amount"},
                **_payee_party(obligation),
            }
        )

    type_map = {
        FinancialComponentType.MAKOLO_FEE.value: FinancialAllocationLineType.PLATFORM,
        FinancialComponentType.TAX.value: FinancialAllocationLineType.TAX,
        FinancialComponentType.PROCESSING_FEE.value: FinancialAllocationLineType.PROCESSING,
        FinancialComponentType.OTHER_FEE.value: FinancialAllocationLineType.OTHER,
    }
    for index, component in enumerate(snapshot.get("components") or []):
        amount = _decimal_money(component.get("amount"), label=f"components[{index}].amount")
        if amount == ZERO:
            continue
        incidence = component.get("incidence")
        if incidence == ChargeIncidence.PLATFORM.value:
            continue
        if incidence not in {ChargeIncidence.PAYER.value, ChargeIncidence.PAYEE.value}:
            raise ValidationError("Incidence financière inconnue dans le snapshot Commerce.")
        line_type = type_map.get(component.get("component_type"), FinancialAllocationLineType.OTHER)
        party = _platform_party() if line_type == FinancialAllocationLineType.PLATFORM else _empty_party()
        specs.append(
            {
                "line_type": line_type,
                "amount": amount,
                "source_component_type": component.get("component_type", ""),
                "source_component_code": component.get("code", ""),
                "source_component_index": index,
                "source_metadata": {
                    "label": component.get("label", ""),
                    "incidence": incidence,
                    "included": bool(component.get("included", False)),
                    "source": component.get("source", ""),
                },
                **party,
            }
        )
    return FinancialAllocationSourceKind.COMMERCE, snapshot, specs


def _obligation_specs(obligation):
    if obligation.reason == PaymentObligationReason.SUBSCRIPTION:
        return (
            FinancialAllocationSourceKind.SUBSCRIPTION,
            {
                "reason": obligation.reason,
                "source_key": obligation.source_key,
                "amount": format(obligation.amount, ".2f"),
                "currency": obligation.currency,
            },
            [
                {
                    "line_type": FinancialAllocationLineType.PLATFORM,
                    "amount": money(obligation.amount),
                    "source_component_type": "subscription",
                    "source_component_code": "subscription_amount",
                    "source_component_index": None,
                    "source_metadata": {"obligation_source_key": obligation.source_key},
                    **_platform_party(),
                }
            ],
        )

    if obligation.payee_platform:
        line_type = FinancialAllocationLineType.PLATFORM
        party = _platform_party()
    else:
        line_type = FinancialAllocationLineType.PAYEE
        party = _payee_party(obligation)
    return (
        FinancialAllocationSourceKind.OBLIGATION,
        {
            "reason": obligation.reason,
            "source_key": obligation.source_key,
            "amount": format(obligation.amount, ".2f"),
            "currency": obligation.currency,
        },
        [
            {
                "line_type": line_type,
                "amount": money(obligation.amount),
                "source_component_type": "payment_obligation",
                "source_component_code": obligation.reason,
                "source_component_index": None,
                "source_metadata": {"obligation_source_key": obligation.source_key},
                **party,
            }
        ],
    )


def _allocation_specs(obligation):
    if obligation.reason == PaymentObligationReason.COMMERCE and obligation.commerce_order_id:
        return _commerce_specs(obligation)
    return _obligation_specs(obligation)


def validate_financial_allocation(allocation):
    lines = list(allocation.lines.all())
    if not lines:
        raise ValidationError("Une allocation complète doit contenir au moins une ligne.")
    total = ZERO
    for line in lines:
        if line.currency != allocation.currency:
            raise ValidationError("Toutes les lignes d’allocation doivent utiliser la devise de l’obligation.")
        total += line.amount
    total = money(total)
    if total != allocation.total_amount or total != allocation.obligation.amount:
        raise ValidationError("L’allocation financière est déséquilibrée.")
    return allocation


@transaction.atomic
def build_financial_allocation(*, obligation):
    obligation = (
        PaymentObligation.objects.select_for_update(of=("self",))
        .select_related("commerce_order", "payee_space", "payee_profile")
        .get(pk=obligation.pk)
    )
    existing = FinancialAllocation.objects.filter(obligation=obligation).first()
    if existing:
        return validate_financial_allocation(existing)

    source_kind, source_snapshot, specs = _allocation_specs(obligation)
    expected_total = money(sum((spec["amount"] for spec in specs), ZERO))
    if expected_total != obligation.amount:
        raise ValidationError("Les composantes économiques ne reconstruisent pas exactement le montant de l’obligation.")

    source_key = f"allocation:obligation:{obligation.pk}"
    try:
        with transaction.atomic():
            allocation = FinancialAllocation.objects.create(
                obligation=obligation,
                source_kind=source_kind,
                source_key=source_key,
                total_amount=obligation.amount,
                currency=obligation.currency,
                source_snapshot=source_snapshot,
            )
            for sequence, spec in enumerate(specs, start=1):
                FinancialAllocationLine.objects.create(
                    allocation=allocation,
                    sequence=sequence,
                    currency=obligation.currency,
                    **spec,
                )
    except IntegrityError as exc:
        concurrent = FinancialAllocation.objects.filter(obligation=obligation).first()
        if concurrent:
            return validate_financial_allocation(concurrent)
        raise ValidationError("Impossible de matérialiser l’allocation de façon unique.") from exc
    return validate_financial_allocation(allocation)


def _entry_type_for_role(role):
    return {
        FinancialAllocationLineType.PAYEE: LedgerEntryType.PAYEE_PAYABLE,
        FinancialAllocationLineType.PLATFORM: LedgerEntryType.PLATFORM_REVENUE,
        FinancialAllocationLineType.TAX: LedgerEntryType.TAX_LIABILITY,
        FinancialAllocationLineType.PROCESSING: LedgerEntryType.PROCESSING_RESERVE,
        FinancialAllocationLineType.OTHER: LedgerEntryType.OTHER_POSITION,
    }[role]


def _create_component_entries(*, allocation, source_kind, source_prefix, payment=None, evidence=None, custody):
    entries = []
    for line in allocation.lines.all():
        entries.append(
            LedgerEntry.objects.create(
                obligation=allocation.obligation,
                allocation=allocation,
                allocation_line=line,
                payment=payment,
                evidence=evidence,
                entry_type=_entry_type_for_role(line.line_type),
                economic_role=line.line_type,
                amount=line.amount,
                currency=allocation.currency,
                source_kind=source_kind,
                source_key=f"{source_prefix}:line:{line.pk}",
                funds_custody=custody,
                metadata={"allocation_line_id": str(line.pk)},
            )
        )
    if money(sum((entry.amount for entry in entries), ZERO)) != allocation.total_amount:
        raise ValidationError("La reconnaissance ledger ne reconstruit pas le montant de l’allocation.")
    return entries


@transaction.atomic
def recognize_payment_financials(*, payment):
    payment = Payment.objects.select_for_update(of=("self",)).select_related("obligation").get(pk=payment.pk)
    if payment.status != PaymentStatus.SUCCEEDED:
        return None
    if not payment.obligation_id:
        return None
    obligation = PaymentObligation.objects.select_for_update(of=("self",)).get(pk=payment.obligation_id)
    if payment.amount != obligation.amount or payment.currency != obligation.currency:
        raise ValidationError("Le Payment réussi ne correspond pas au montant/devise de son obligation.")
    marker_key = f"ledger:payment:{payment.pk}:recognized"
    if LedgerEntry.objects.filter(source_key=marker_key).exists():
        return build_financial_allocation(obligation=obligation)
    allocation = build_financial_allocation(obligation=obligation)
    LedgerEntry.objects.create(
        obligation=obligation,
        allocation=allocation,
        payment=payment,
        entry_type=LedgerEntryType.PAYMENT_RECOGNIZED,
        economic_role="",
        amount=payment.amount,
        currency=payment.currency,
        source_kind=LedgerSourceKind.PAYMENT,
        source_key=marker_key,
        funds_custody=FundsCustody.UNKNOWN,
        metadata={"payment_reference": payment.reference},
        occurred_at=payment.succeeded_at or payment.processed_at,
    )
    _create_component_entries(
        allocation=allocation,
        source_kind=LedgerSourceKind.PAYMENT,
        source_prefix=f"ledger:payment:{payment.pk}",
        payment=payment,
        custody=FundsCustody.UNKNOWN,
    )
    return allocation


@transaction.atomic
def recognize_evidence_financials(*, evidence):
    evidence = (
        PaymentEvidence.objects.select_for_update(of=("self",))
        .select_related("obligation")
        .get(pk=evidence.pk)
    )
    if evidence.status != PaymentEvidenceStatus.VERIFIED:
        return None
    obligation = PaymentObligation.objects.select_for_update(of=("self",)).get(pk=evidence.obligation_id)
    marker_key = f"ledger:evidence:{evidence.pk}:recognized"
    if LedgerEntry.objects.filter(source_key=marker_key).exists():
        return build_financial_allocation(obligation=obligation)
    allocation = build_financial_allocation(obligation=obligation)
    LedgerEntry.objects.create(
        obligation=obligation,
        allocation=allocation,
        evidence=evidence,
        entry_type=LedgerEntryType.PAYMENT_RECOGNIZED,
        economic_role="",
        amount=obligation.amount,
        currency=obligation.currency,
        source_kind=LedgerSourceKind.PAYMENT_EVIDENCE,
        source_key=marker_key,
        funds_custody=FundsCustody.EXTERNAL,
        metadata={"external_reference": evidence.external_reference},
        occurred_at=evidence.paid_at,
    )
    _create_component_entries(
        allocation=allocation,
        source_kind=LedgerSourceKind.PAYMENT_EVIDENCE,
        source_prefix=f"ledger:evidence:{evidence.pk}",
        evidence=evidence,
        custody=FundsCustody.EXTERNAL,
    )
    return allocation


def _refund_breakdown(refund, allocation):
    lines = {str(line.pk): line for line in allocation.lines.all()}
    if refund.amount == refund.payment.amount and not refund.financial_breakdown:
        return [(line, line.amount) for line in lines.values()]
    if not refund.financial_breakdown:
        raise ValidationError("Un remboursement partiel exige une décomposition explicite par ligne d’allocation.")
    result = []
    seen = set()
    for item in refund.financial_breakdown:
        line_id = str(item.get("allocation_line_id", ""))
        if line_id in seen or line_id not in lines:
            raise ValidationError("Décomposition de remboursement invalide ou dupliquée.")
        amount = _decimal_money(item.get("amount"), label="refund.financial_breakdown.amount")
        line = lines[line_id]
        if amount <= ZERO or amount > line.amount:
            raise ValidationError("Le montant remboursé par composante est invalide.")
        seen.add(line_id)
        result.append((line, amount))
    if money(sum((amount for _, amount in result), ZERO)) != refund.amount:
        raise ValidationError("La décomposition du remboursement ne correspond pas à son montant.")
    return result


@transaction.atomic
def record_refund_financials(*, refund):
    refund = (
        Refund.objects.select_for_update(of=("self",))
        .select_related("payment__obligation")
        .get(pk=refund.pk)
    )
    if refund.status != RefundStatus.SUCCEEDED:
        return None
    payment = refund.payment
    if not payment.obligation_id:
        return None
    obligation = PaymentObligation.objects.select_for_update(of=("self",)).get(pk=payment.obligation_id)
    if refund.currency != obligation.currency or refund.amount > payment.amount:
        raise ValidationError("Le Refund ne correspond pas au montant/devise de la transaction d’origine.")
    marker_key = f"ledger:refund:{refund.pk}:recognized"
    if LedgerEntry.objects.filter(source_key=marker_key).exists():
        return build_financial_allocation(obligation=obligation)
    allocation = build_financial_allocation(obligation=obligation)
    breakdown = _refund_breakdown(refund, allocation)
    LedgerEntry.objects.create(
        obligation=obligation,
        allocation=allocation,
        payment=payment,
        refund=refund,
        entry_type=LedgerEntryType.REFUND,
        economic_role="",
        amount=-refund.amount,
        currency=refund.currency,
        source_kind=LedgerSourceKind.REFUND,
        source_key=marker_key,
        funds_custody=FundsCustody.UNKNOWN,
        metadata={"refund_reference": refund.reference},
        occurred_at=refund.processed_at,
    )
    reversed_total = ZERO
    for line, amount in breakdown:
        LedgerEntry.objects.create(
            obligation=obligation,
            allocation=allocation,
            allocation_line=line,
            payment=payment,
            refund=refund,
            entry_type=LedgerEntryType.REVERSAL,
            economic_role=line.line_type,
            amount=-amount,
            currency=refund.currency,
            source_kind=LedgerSourceKind.REFUND,
            source_key=f"ledger:refund:{refund.pk}:line:{line.pk}",
            funds_custody=FundsCustody.UNKNOWN,
            metadata={"reverses_allocation_line_id": str(line.pk)},
            occurred_at=refund.processed_at,
        )
        reversed_total += amount
    if money(reversed_total) != refund.amount:
        raise ValidationError("Les contre-écritures du remboursement sont déséquilibrées.")
    return allocation


@transaction.atomic
def record_financial_adjustment(*, obligation, economic_role, amount, currency, reason, idempotency_key, actor):
    if not getattr(actor, "is_authenticated", False) or not has_platform_authority(actor):
        raise PermissionDenied("Un ajustement financier manuel exige une autorité plateforme explicite.")
    if economic_role not in FinancialAllocationLineType.values:
        raise ValidationError("Rôle économique d’ajustement inconnu.")
    amount = _decimal_money(amount, label="adjustment.amount")
    if amount == ZERO:
        raise ValidationError("Un ajustement financier ne peut pas être nul.")
    if (currency or "").upper() != obligation.currency:
        raise ValidationError("Un ajustement doit utiliser la devise de l’obligation.")
    reason = (reason or "").strip()
    if not reason or not idempotency_key:
        raise ValidationError("Un ajustement exige une raison et une clé d’idempotence.")
    obligation = PaymentObligation.objects.select_for_update(of=("self",)).get(pk=obligation.pk)
    allocation = build_financial_allocation(obligation=obligation)
    source_key = f"ledger:adjustment:{idempotency_key}"[:220]
    existing = LedgerEntry.objects.filter(source_key=source_key).first()
    if existing:
        if existing.obligation_id != obligation.pk or existing.amount != amount or existing.economic_role != economic_role:
            raise ValidationError("Cette clé d’ajustement correspond à une autre correction financière.")
        return existing
    return LedgerEntry.objects.create(
        obligation=obligation,
        allocation=allocation,
        entry_type=LedgerEntryType.ADJUSTMENT,
        economic_role=economic_role,
        amount=amount,
        currency=obligation.currency,
        source_kind=LedgerSourceKind.ADJUSTMENT,
        source_key=source_key,
        funds_custody=FundsCustody.UNKNOWN,
        metadata={"reason": reason, "actor_id": str(actor.pk)},
    )
