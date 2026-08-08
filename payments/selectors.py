from django.db.models import Q

from events.permissions import user_can_manage_events

from .models import Payment, PaymentEvent, Refund


def get_payments_visible_to(user):
    queryset = Payment.objects.select_related(
        "order",
        "order__event",
        "order__event__organizer",
        "order__buyer",
        "initiated_by",
    ).prefetch_related("refunds")
    if not user.is_authenticated:
        return queryset.none()
    if user.is_staff:
        return queryset

    filters = Q(order__buyer=user) | Q(initiated_by=user)
    if user_can_manage_events(user):
        filters |= Q(order__event__organizer=user)
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
    )
    if not user.is_authenticated:
        return queryset.none()
    if user.is_staff:
        return queryset
    if user_can_manage_events(user):
        return queryset.filter(payment__order__event__organizer=user)
    return queryset.none()
