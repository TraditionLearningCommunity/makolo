from decimal import Decimal

from django.db.models import Q, Sum

from access.models import Access
from commerce.models import CommerceOrder, CommerceOrderStatus
from journeys.models import Journey
from payments.models import Payment, PaymentStatus


def contact_relationship_metrics(contact, *, include_financials=False):
    """Return small canonical CRM metrics for a Space/Profile relationship.

    This deliberately does not replace the historical Event-oriented Customer 360.
    New cross-domain reads prefer Journey, Access, CommerceOrder and Payment.
    """
    if not contact.user_id:
        return {
            "journeys": 0,
            "accesses": 0,
            "confirmed_orders": 0,
            "financial": None,
        }

    journeys = Journey.objects.filter(activity__space=contact.organization, beneficiary_id=contact.user_id)
    accesses = Access.objects.filter(activity__space=contact.organization, beneficiary_id=contact.user_id)
    orders = CommerceOrder.objects.filter(payee_space=contact.organization).filter(
        Q(buyer_id=contact.user_id) | Q(journey__beneficiary_id=contact.user_id)
    )
    confirmed = orders.filter(status=CommerceOrderStatus.CONFIRMED)

    financial = None
    if include_financials:
        spend = confirmed.values("currency").annotate(amount=Sum("total")).order_by("currency")
        successful_payments = (
            Payment.objects.filter(commerce_order__in=confirmed, status=PaymentStatus.SUCCEEDED)
            .values("currency")
            .annotate(amount=Sum("amount"))
            .order_by("currency")
        )
        financial = {
            "order_value_by_currency": [
                {"currency": row["currency"], "amount": row["amount"] or Decimal("0.00")}
                for row in spend
            ],
            "successful_payments_by_currency": [
                {"currency": row["currency"], "amount": row["amount"] or Decimal("0.00")}
                for row in successful_payments
            ],
        }

    return {
        "journeys": journeys.count(),
        "accesses": accesses.count(),
        "confirmed_orders": confirmed.count(),
        "financial": financial,
    }
