"""Owner-side, optional monetary indication; never a withdrawal authorization."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .models import RecognitionCreditValuation


def credit_money_equivalent(account):
    """Return a display amount only when an operator explicitly enabled it.

    The exchange multiplier is private to Recognition and Makolo Platform.
    Pending credits, financial payout rights and foreign Loyalty points are
    intentionally excluded.
    """
    if account is None or account.points_balance <= 0:
        return None
    valuation = RecognitionCreditValuation.objects.filter(
        pk=1, is_active=True,
    ).first()
    if valuation is None:
        return None
    try:
        amount = (
            Decimal(account.points_balance) * valuation.amount_per_credit
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, OverflowError):
        return None
    if amount <= 0:
        return None
    return {
        "amount": format(amount, ".2f"),
        "currency": valuation.currency,
    }
