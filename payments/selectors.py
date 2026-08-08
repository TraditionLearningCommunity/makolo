from django.db.models import Q

from organizations.permissions import FINANCE_ROLES

from .models import Payment, PaymentEvent, Refund


def _organization_finance_filter(prefix: str, user) -> Q:
    return Q(
        **{
            f"{prefix}organization__memberships__user": user,
            f"{prefix}organization__memberships__is_active": True,
            f"{prefix}organization__memberships__role__in": FINANCE_ROLES,
        }
    )


def get_payments_visible_to(user):
    queryset = Payment.objects.select_related(
        "order",
        "order__event",
        "order__event__organizer",
        "order__event__organization",
        "order__buyer",
        "initiated_by",
    ).prefetch_related("refunds")
    if not user.is_authenticated:
        return queryset.none()
    if user.is_staff:
        return queryset

    # Financial data is intentionally narrower than general event management.
    # Buyers see their own payments; historical legacy organizers keep access;
    # organization access is granted only to finance-capable roles.
    filters = (
        Q(order__buyer=user)
        | Q(initiated_by=user)
        | Q(order__event__organizer=user)
        | _organization_finance_filter("order__event__", user)
    )
    return queryset.filter(filters).distinct()


def get_refunds_visible_to(user):
    payment_ids = get_payments_visible_to(user).values("pk")
    return Refund.objects.select_related(
        "payment",
        "payment__order",
        "payment__order__event",
        "requested_by",
    ).filter(payment_id__in=payment_ids)


def get_payment_events_visible_to(user):
    queryset = PaymentEvent.objects.select_related(
        "payment",
        "payment__order",
        "payment__order__event",
        "payment__order__event__organizer",
        "payment__order__event__organization",
    )
    if not user.is_authenticated:
        return queryset.none()
    if user.is_staff:
        return queryset

    return queryset.filter(
        Q(payment__order__event__organizer=user)
        | _organization_finance_filter("payment__order__event__", user)
    ).distinct()
