from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from access.models import Access, AccessStatus, AccessUse, AccessUseResult
from capacity.models import CapacityPool, CapacityReservationStatus
from commerce.models import CommerceOrder, CommerceOrderStatus
from journeys.models import Journey, JourneyRequest, JourneyStatus, RequestStatus, WorkflowKind
from payments.models import Payment, PaymentStatus, Refund, RefundStatus


CONFIRMED_COMMERCE_STATUSES = {CommerceOrderStatus.CONFIRMED, CommerceOrderStatus.REFUNDED}
SUCCESSFUL_PAYMENT_STATUSES = {PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED}


def _percent(numerator, denominator):
    if not denominator:
        return None
    return round((numerator / denominator) * 100, 1)


def _journeys(activity, occurrence=None):
    qs = Journey.objects.filter(activity=activity)
    return qs.filter(occurrence=occurrence) if occurrence is not None else qs


def journey_funnel(activity, occurrence=None):
    qs = _journeys(activity, occurrence)
    workflow_rows = qs.values("workflow").annotate(total=Count("id"))
    requests = JourneyRequest.objects.filter(journey__in=qs)
    return {
        "total": qs.count(),
        "submitted": qs.filter(submitted_at__isnull=False).count(),
        "approved": qs.filter(
            Q(status=JourneyStatus.APPROVED)
            | Q(status=JourneyStatus.PENDING_PAYMENT)
            | Q(status=JourneyStatus.CONFIRMED)
            | Q(status=JourneyStatus.FULFILLED)
        ).count(),
        "confirmed": qs.filter(confirmed_at__isnull=False).count(),
        "fulfilled": qs.filter(fulfilled_at__isnull=False).count(),
        "cancelled": qs.filter(status=JourneyStatus.CANCELLED).count(),
        "requests_approved": requests.filter(status=RequestStatus.APPROVED).count(),
        "requests_rejected": requests.filter(status=RequestStatus.REJECTED).count(),
        "workflows": {row["workflow"]: row["total"] for row in workflow_rows},
    }


def access_summary(activity, occurrence=None):
    accesses = Access.objects.filter(activity=activity)
    uses = AccessUse.objects.filter(access__activity=activity)
    if occurrence is not None:
        accesses = accesses.filter(occurrence=occurrence)
        uses = uses.filter(occurrence=occurrence)
    issued = accesses.count()
    active = accesses.filter(status__in=[AccessStatus.VALID, AccessStatus.USED]).count()
    used = uses.filter(result=AccessUseResult.ACCEPTED).values("access_id").distinct().count()
    revoked = accesses.filter(status=AccessStatus.REVOKED).count()
    refused = uses.exclude(result=AccessUseResult.ACCEPTED).count()
    return {
        "issued": issued,
        "active": active,
        "used": used,
        "revoked": revoked,
        "refused_attempts": refused,
        "usage_rate": _percent(used, issued),
    }


def commerce_summary(activity, occurrence=None):
    orders = CommerceOrder.objects.filter(journey__activity=activity)
    if occurrence is not None:
        orders = orders.filter(journey__occurrence=occurrence)
    confirmed = orders.filter(status__in=CONFIRMED_COMMERCE_STATUSES)
    rows = (
        confirmed.filter(total__gt=0)
        .values("currency")
        .annotate(
            subtotal=Sum("subtotal"),
            discounts=Sum("discount_total"),
            total=Sum("total"),
        )
        .order_by("currency")
    )
    return {
        "orders_total": orders.count(),
        "confirmed_orders": confirmed.count(),
        "pending_orders": orders.filter(status=CommerceOrderStatus.PENDING).count(),
        "cancelled_orders": orders.filter(status=CommerceOrderStatus.CANCELLED).count(),
        "expired_orders": orders.filter(status=CommerceOrderStatus.EXPIRED).count(),
        "commercial_value": [
            {
                "currency": row["currency"],
                "subtotal": row["subtotal"] or Decimal("0.00"),
                "discounts": row["discounts"] or Decimal("0.00"),
                "total": row["total"] or Decimal("0.00"),
            }
            for row in rows
        ],
    }


def _payment_scope_filter(activity, occurrence=None):
    canonical = Q(commerce_order__journey__activity=activity)
    legacy = Q(commerce_order__isnull=True, order__event__activity=activity)
    scope = canonical | legacy
    if occurrence is None:
        return scope
    return (
        Q(commerce_order__journey__occurrence=occurrence)
        | Q(
            commerce_order__isnull=True,
            order__event__activity=activity,
            order__event__start_at=occurrence.start_at,
            order__event__end_at=occurrence.end_at,
        )
    )


def _refund_scope_filter(activity, occurrence=None):
    canonical = Q(payment__commerce_order__journey__activity=activity)
    legacy = Q(
        payment__commerce_order__isnull=True,
        payment__order__event__activity=activity,
    )
    if occurrence is None:
        return canonical | legacy
    return (
        Q(payment__commerce_order__journey__occurrence=occurrence)
        | Q(
            payment__commerce_order__isnull=True,
            payment__order__event__activity=activity,
            payment__order__event__start_at=occurrence.start_at,
            payment__order__event__end_at=occurrence.end_at,
        )
    )


def payment_summary(activity, occurrence=None):
    # Payment is provider truth. Prefer the CommerceOrder/ Journey relation, but
    # retain an explicit Event fallback only while a historical Payment has not
    # been bridged. The mutually exclusive commerce_order NULL predicate ensures
    # one Payment row can never be counted twice.
    payments = Payment.objects.filter(_payment_scope_filter(activity, occurrence)).distinct()
    refunds = Refund.objects.filter(
        _refund_scope_filter(activity, occurrence),
        status=RefundStatus.SUCCEEDED,
    ).distinct()

    gross_rows = (
        payments.filter(status__in=SUCCESSFUL_PAYMENT_STATUSES)
        .values("currency")
        .annotate(total=Sum("amount"))
    )
    refund_rows = refunds.values("currency").annotate(total=Sum("amount"))
    gross = {row["currency"]: row["total"] or Decimal("0.00") for row in gross_rows}
    refunded = {row["currency"]: row["total"] or Decimal("0.00") for row in refund_rows}
    currencies = sorted(set(gross) | set(refunded))
    return {
        "attempts": payments.count(),
        "succeeded": payments.filter(status__in=SUCCESSFUL_PAYMENT_STATUSES).count(),
        "failed": payments.filter(status=PaymentStatus.FAILED).count(),
        "collected": [
            {
                "currency": currency,
                "gross": gross.get(currency, Decimal("0.00")),
                "refunds": refunded.get(currency, Decimal("0.00")),
                "net": gross.get(currency, Decimal("0.00")) - refunded.get(currency, Decimal("0.00")),
            }
            for currency in currencies
        ],
    }


def capacity_summary(activity, occurrence=None):
    now = timezone.now()
    pools = CapacityPool.objects.filter(activity=activity)
    if occurrence is not None:
        pools = pools.filter(occurrence=occurrence)
    pools = pools.annotate(
        held_value=Sum(
            "reservations__quantity",
            filter=Q(reservations__status=CapacityReservationStatus.HELD)
            & (Q(reservations__expires_at__isnull=True) | Q(reservations__expires_at__gt=now)),
        ),
        committed_value=Sum(
            "reservations__quantity",
            filter=Q(reservations__status=CapacityReservationStatus.COMMITTED),
        ),
    ).select_related("activity", "occurrence")

    details = []
    aggregate_held = 0
    aggregate_committed = 0
    aggregate_total = 0
    aggregate_available = 0
    unlimited = False
    for pool in pools:
        held = pool.held_value or 0
        committed = pool.committed_value or 0
        total = pool.total_quantity
        available = None if total is None else max(total - held - committed, 0)
        unlimited = unlimited or total is None
        aggregate_held += held
        aggregate_committed += committed
        if total is not None:
            aggregate_total += total
            aggregate_available += available
        details.append(
            {
                "pool_id": str(pool.pk),
                "label": pool.label,
                "total": total,
                "held": held,
                "committed": committed,
                "available": available,
            }
        )
    return {
        "total": None if unlimited else aggregate_total,
        "held": aggregate_held,
        "committed": aggregate_committed,
        "available": None if unlimited else aggregate_available,
        "utilization_rate": (
            None if unlimited or aggregate_total == 0
            else _percent(aggregate_held + aggregate_committed, aggregate_total)
        ),
        "pools": details,
    }


def activity_summary(activity):
    return {
        "activity": activity,
        "journey": journey_funnel(activity),
        "access": access_summary(activity),
        "commerce": commerce_summary(activity),
        "payment": payment_summary(activity),
        "capacity": capacity_summary(activity),
    }


def occurrence_summary(occurrence):
    return {
        "activity": occurrence.activity,
        "occurrence": occurrence,
        "journey": journey_funnel(occurrence.activity, occurrence),
        "access": access_summary(occurrence.activity, occurrence),
        "commerce": commerce_summary(occurrence.activity, occurrence),
        "payment": payment_summary(occurrence.activity, occurrence),
        "capacity": capacity_summary(occurrence.activity, occurrence),
    }


def space_summary(space):
    activities = space.activities.all()
    journey_qs = Journey.objects.filter(activity__space=space)
    access_qs = Access.objects.filter(activity__space=space)
    order_qs = CommerceOrder.objects.filter(journey__activity__space=space)
    payment_qs = Payment.objects.filter(
        Q(commerce_order__journey__activity__space=space)
        | Q(commerce_order__isnull=True, order__event__organization=space)
    ).distinct()
    commercial_rows = (
        order_qs.filter(status__in=CONFIRMED_COMMERCE_STATUSES, total__gt=0)
        .values("currency").annotate(total=Sum("total")).order_by("currency")
    )
    paid_rows = (
        payment_qs.filter(status__in=SUCCESSFUL_PAYMENT_STATUSES)
        .values("currency").annotate(total=Sum("amount")).order_by("currency")
    )
    return {
        "activities": activities.count(),
        "journeys": journey_qs.count(),
        "access_issued": access_qs.count(),
        "orders": order_qs.count(),
        "commercial_value": {row["currency"]: row["total"] for row in commercial_rows},
        "payment_gross": {row["currency"]: row["total"] for row in paid_rows},
        "workflows": {
            workflow: journey_qs.filter(workflow=workflow).count()
            for workflow in WorkflowKind.values
        },
    }
