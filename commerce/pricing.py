from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import StrEnum

from django.core.exceptions import ValidationError


MONEY_QUANTUM = Decimal("0.01")
ZERO = Decimal("0.00")


class PricingPolicy(StrEnum):
    SELLER_NET_GUARANTEED = "seller_net_guaranteed"
    CUSTOMER_TOTAL_FIXED = "customer_total_fixed"


class FinancialComponentType(StrEnum):
    BASE_PRICE = "base_price"
    DISCOUNT = "discount"
    MAKOLO_FEE = "makolo_fee"
    PROCESSING_FEE = "processing_fee"
    TAX = "tax"
    OTHER_FEE = "other_fee"


class ChargeIncidence(StrEnum):
    PAYER = "payer"
    PAYEE = "payee"
    PLATFORM = "platform"


class ChargeScope(StrEnum):
    ORDER = "order"
    LINE = "line"
    UNIT = "unit"


@dataclass(frozen=True)
class ChargeRule:
    code: str
    label: str
    component_type: FinancialComponentType
    incidence: ChargeIncidence
    fixed_amount: Decimal = ZERO
    percentage_rate: Decimal = ZERO
    scope: ChargeScope = ChargeScope.ORDER
    included: bool = False
    source: str = ""

    def __post_init__(self):
        object.__setattr__(self, "fixed_amount", _decimal(self.fixed_amount))
        object.__setattr__(self, "percentage_rate", _decimal(self.percentage_rate))
        if self.component_type == FinancialComponentType.BASE_PRICE:
            raise ValidationError("Une ChargeRule ne peut pas être de type base_price.")
        if self.component_type == FinancialComponentType.DISCOUNT:
            raise ValidationError("Les remises sont fournies séparément au moteur F1.")
        if self.fixed_amount < ZERO or self.percentage_rate < ZERO:
            raise ValidationError("Une charge ne peut pas avoir un montant ou taux négatif.")
        if self.fixed_amount == ZERO and self.percentage_rate == ZERO:
            raise ValidationError("Une charge doit définir un montant fixe, un taux, ou les deux.")
        if self.scope != ChargeScope.ORDER:
            raise ValidationError("F1 expose les scopes line/unit mais ne calcule actuellement que le scope order.")
        if self.included and self.incidence == ChargeIncidence.PAYER:
            raise ValidationError("Une charge incluse ne peut pas être ajoutée au payeur.")


@dataclass(frozen=True)
class FinancialLine:
    code: str
    label: str
    component_type: FinancialComponentType
    incidence: ChargeIncidence
    amount: Decimal
    calculation_base: Decimal
    fixed_amount: Decimal
    percentage_rate: Decimal
    scope: ChargeScope
    included: bool = False
    source: str = ""

    def as_dict(self):
        return {
            "code": self.code,
            "label": self.label,
            "component_type": self.component_type.value,
            "incidence": self.incidence.value,
            "amount": _money_text(self.amount),
            "calculation_base": _money_text(self.calculation_base),
            "fixed_amount": _money_text(self.fixed_amount),
            "percentage_rate": str(self.percentage_rate),
            "scope": self.scope.value,
            "included": self.included,
            "source": self.source,
        }


@dataclass(frozen=True)
class FinancialQuote:
    currency: str
    pricing_policy: PricingPolicy
    subtotal: Decimal
    discount_total: Decimal
    net_base: Decimal
    lines: tuple[FinancialLine, ...]
    payer_total: Decimal
    expected_payee_amount: Decimal
    makolo_amount: Decimal

    def __post_init__(self):
        if self.payer_total < ZERO or self.expected_payee_amount < ZERO:
            raise ValidationError("Les résultats financiers ne peuvent pas être négatifs.")

    def as_snapshot(self):
        return {
            "version": 1,
            "currency": self.currency,
            "pricing_policy": self.pricing_policy.value,
            "subtotal": _money_text(self.subtotal),
            "discount_total": _money_text(self.discount_total),
            "net_base": _money_text(self.net_base),
            "components": [line.as_dict() for line in self.lines],
            "payer_total": _money_text(self.payer_total),
            "expected_payee_amount": _money_text(self.expected_payee_amount),
            "makolo_amount": _money_text(self.makolo_amount),
            "rounding": "ROUND_HALF_UP",
            "money_quantum": str(MONEY_QUANTUM),
        }


def _decimal(value) -> Decimal:
    if isinstance(value, float):
        raise ValidationError("Les floats sont interdits pour les calculs financiers.")
    try:
        return value if isinstance(value, Decimal) else Decimal(str(value))
    except Exception as exc:  # Decimal raises several concrete parse errors.
        raise ValidationError("Montant financier invalide.") from exc


def money(value) -> Decimal:
    return _decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _money_text(value) -> str:
    return format(money(value), ".2f")


def _currency(value: str) -> str:
    normalized = (value or "").strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise ValidationError("La devise doit être un code de trois lettres.")
    return normalized


def _line_from_rule(rule: ChargeRule, *, calculation_base: Decimal) -> FinancialLine:
    raw = rule.fixed_amount + (calculation_base * rule.percentage_rate)
    return FinancialLine(
        code=rule.code,
        label=rule.label,
        component_type=rule.component_type,
        incidence=rule.incidence,
        amount=money(raw),
        calculation_base=calculation_base,
        fixed_amount=rule.fixed_amount,
        percentage_rate=rule.percentage_rate,
        scope=rule.scope,
        included=rule.included,
        source=rule.source,
    )


def calculate_quote(
    *,
    currency: str,
    subtotal,
    discount_total=ZERO,
    pricing_policy: PricingPolicy | str = PricingPolicy.SELLER_NET_GUARANTEED,
    charges=(),
) -> FinancialQuote:
    currency = _currency(currency)
    subtotal = money(subtotal)
    discount_total = money(discount_total)
    try:
        pricing_policy = PricingPolicy(pricing_policy)
    except ValueError as exc:
        raise ValidationError("Politique tarifaire inconnue.") from exc
    if subtotal < ZERO or discount_total < ZERO or discount_total > subtotal:
        raise ValidationError("Sous-total ou remise incohérent.")

    net_base = money(subtotal - discount_total)
    lines = tuple(_line_from_rule(rule, calculation_base=net_base) for rule in charges)

    payer_charges = money(sum((line.amount for line in lines if line.incidence == ChargeIncidence.PAYER), ZERO))
    payee_charges = money(sum((line.amount for line in lines if line.incidence == ChargeIncidence.PAYEE), ZERO))
    makolo_amount = money(
        sum((line.amount for line in lines if line.component_type == FinancialComponentType.MAKOLO_FEE), ZERO)
    )

    if pricing_policy == PricingPolicy.SELLER_NET_GUARANTEED:
        if payee_charges:
            raise ValidationError("SELLER_NET_GUARANTEED est incompatible avec une charge supportée par le bénéficiaire.")
        payer_total = money(net_base + payer_charges)
        expected_payee_amount = net_base
    else:
        if payer_charges:
            raise ValidationError("CUSTOMER_TOTAL_FIXED est incompatible avec une charge ajoutée au-dessus du total client.")
        payer_total = net_base
        expected_payee_amount = money(net_base - payee_charges)
        if expected_payee_amount < ZERO:
            raise ValidationError("Les charges supportées par le bénéficiaire dépassent le total client fixé.")

    reconstructed_payer_total = money(net_base + (payer_charges if pricing_policy == PricingPolicy.SELLER_NET_GUARANTEED else ZERO))
    if reconstructed_payer_total != payer_total:
        raise ValidationError("Le détail financier ne reconstruit pas exactement le total payeur.")

    return FinancialQuote(
        currency=currency,
        pricing_policy=pricing_policy,
        subtotal=subtotal,
        discount_total=discount_total,
        net_base=net_base,
        lines=lines,
        payer_total=payer_total,
        expected_payee_amount=expected_payee_amount,
        makolo_amount=makolo_amount,
    )
