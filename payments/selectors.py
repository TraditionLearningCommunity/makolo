from django.db.models import Q

from authorization.constants import PermissionCode
from authorization.services import space_ids_with_permission

from .models import Payment, PaymentEvent, Refund


def _space_filter(prefix: str, space_ids) -> Q:
    if not space_ids:
        return Q(pk__isnull=True)
    return Q(**{f"{prefix}organization_id__in": space_ids})


def get_payments_visible_to(user):
    queryset = Payment.objects.select_related(
        "order",
        "order__event",
        "order__event__organizer",
        "order__event__organization",
        "order__buyer",
        "initiated_by",
    ).prefetch_related("refunds")
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    space_ids = space_ids_with_permission(user, PermissionCode.FINANCE_VIEW)
    if space_ids is None:
        return queryset
    contextual = _space_filter("order__event__", space_ids)
    return queryset.filter(
        Q(order__buyer=user)
        | Q(initiated_by=user)
        | contextual
        | Q(order__event__organization__isnull=True, order__event__organizer=user)
    ).distinct()


def get_refunds_visible_to(user):
    payment_ids = get_payments_visible_to(user).values("pk")
    return Refund.objects.select_related(
        "payment", "payment__order", "payment__order__event", "requested_by"
    ).filter(payment_id__in=payment_ids)


def get_payment_events_visible_to(user):
    queryset = PaymentEvent.objects.select_related(
        "payment",
        "payment__order",
        "payment__order__event",
        "payment__order__event__organizer",
        "payment__order__event__organization",
    )
    if not getattr(user, "is_authenticated", False):
        return queryset.none()

    space_ids = space_ids_with_permission(user, PermissionCode.FINANCE_VIEW)
    if space_ids is None:
        return queryset
    contextual = _space_filter("payment__order__event__", space_ids)
    return queryset.filter(
        contextual
        | Q(
            payment__order__event__organization__isnull=True,
            payment__order__event__organizer=user,
        )
    ).distinct()
