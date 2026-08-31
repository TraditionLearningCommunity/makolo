from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import CommerceOrder, CommerceOrderStatus
from .pricing import (
    ChargeIncidence,
    ChargeRule,
    ChargeScope,
    FinancialComponentType,
)
from .services import quote_financials


def _charge_rules_from_snapshot(snapshot):
    rules = []
    for component in (snapshot or {}).get("components", []):
        rules.append(
            ChargeRule(
                code=component["code"],
                label=component["label"],
                component_type=FinancialComponentType(component["component_type"]),
                incidence=ChargeIncidence(component["incidence"]),
                fixed_amount=Decimal(component["fixed_amount"]),
                percentage_rate=Decimal(component["percentage_rate"]),
                scope=ChargeScope(component.get("scope", ChargeScope.ORDER.value)),
                included=bool(component.get("included", False)),
                source=component.get("source", ""),
            )
        )
    return rules


@transaction.atomic
def requote_pending_order(*, order, discount_total):
    """Re-price a mutable Commerce order from its own snapshotted terms.

    This is intentionally limited to draft/pending orders. Confirmed historical
    orders remain immutable, while a pre-payment Promotion can still change the
    discount without consulting mutable current pricing configuration.
    """

    order = CommerceOrder.objects.select_for_update(of=("self",)).order_by().get(pk=order.pk)
    if order.status not in {CommerceOrderStatus.DRAFT, CommerceOrderStatus.PENDING}:
        raise ValidationError("Seule une commande Commerce non finalisée peut être recalculée.")

    quote = quote_financials(
        currency=order.currency,
        subtotal=order.subtotal,
        discount_total=discount_total,
        pricing_policy=order.pricing_policy,
        charges=_charge_rules_from_snapshot(order.financial_snapshot),
    )
    order.discount_total = quote.discount_total
    order.total = quote.payer_total
    order.expected_payee_amount = quote.expected_payee_amount
    order.makolo_amount = quote.makolo_amount
    order.financial_snapshot = quote.as_snapshot()
    order._allow_financial_snapshot_write = True
    order.save(
        update_fields=[
            "discount_total",
            "total",
            "expected_payee_amount",
            "makolo_amount",
            "financial_snapshot",
            "updated_at",
        ]
    )
    return order
