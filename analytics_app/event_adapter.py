from datetime import timedelta

from django.db.models import Count, Q
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone

from access.models import Access, AccessStatus, AccessUse, AccessUseResult
from tickets.models import TicketType, TicketTransfer, TicketWaitlistEntry, TransferStatus, WaitlistStatus

from .canonical import activity_summary
from .permissions import user_can_view_event_financials
from .services import _build_insights


def _percent(numerator, denominator):
    if not denominator:
        return None
    return round((numerator / denominator) * 100, 1)


def _access_series(activity, days):
    days = min(max(int(days or 30), 7), 90)
    today = timezone.localdate()
    start_day = today - timedelta(days=days - 1)
    rows = (
        Access.objects.filter(activity=activity, created_at__date__gte=start_day)
        .annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(quantity=Count("id"))
        .order_by("day")
    )
    values = {row["day"]: row["quantity"] for row in rows}
    maximum = max(values.values(), default=0)
    return [
        {
            "date": (start_day + timedelta(days=offset)).isoformat(),
            "label": (start_day + timedelta(days=offset)).strftime("%d/%m"),
            "quantity": values.get(start_day + timedelta(days=offset), 0),
            "bar_width": (
                round((values.get(start_day + timedelta(days=offset), 0) / maximum) * 100, 1)
                if maximum else 0
            ),
        }
        for offset in range(days)
    ]


def _access_use_series(activity):
    rows = list(
        AccessUse.objects.filter(access__activity=activity, result=AccessUseResult.ACCEPTED)
        .annotate(hour=TruncHour("used_at"))
        .values("hour")
        .annotate(quantity=Count("id"))
        .order_by("hour")
    )
    maximum = max((row["quantity"] for row in rows), default=0)
    return [
        {
            "hour": row["hour"].isoformat() if row["hour"] else None,
            "label": timezone.localtime(row["hour"]).strftime("%d/%m %H:%M") if row["hour"] else "",
            "quantity": row["quantity"],
            "bar_width": round((row["quantity"] / maximum) * 100, 1) if maximum else 0,
        }
        for row in rows[-24:]
    ]


def _ticket_type_breakdown(event):
    rows = TicketType.objects.select_related("offer", "capacity_pool").filter(event=event).annotate(
        active_count=Count(
            "tickets__access",
            filter=Q(tickets__access__status__in=[AccessStatus.VALID, AccessStatus.USED]),
            distinct=True,
        ),
        used_count=Count(
            "tickets__access",
            filter=Q(tickets__access__uses__result=AccessUseResult.ACCEPTED),
            distinct=True,
        ),
        waiting_count=Count(
            "waitlist_entries",
            filter=Q(waitlist_entries__status=WaitlistStatus.WAITING),
            distinct=True,
        ),
    )
    result = []
    for row in rows:
        available = row.available_quantity
        total = row.quantity_total
        result.append(
            {
                "id": str(row.pk),
                "name": row.name,
                "price": row.price,
                "currency": row.currency,
                "quantity_total": total,
                "reserved_quantity": row.reserved_quantity,
                "issued_quantity": row.issued_quantity,
                "active_count": row.active_count,
                "used_count": row.used_count,
                "waiting_count": row.waiting_count,
                "available_quantity": available,
                "sell_through_percent": _percent(row.active_count, total) if total else None,
            }
        )
    return result


def _forecast(event, active_access, capacity):
    if capacity is None or active_access <= 0 or event.status != "published":
        return None
    remaining = max(capacity - active_access, 0)
    if remaining == 0:
        return {
            "state": "sold_out",
            "remaining": 0,
            "tickets_per_day": None,
            "predicted_sellout_at": None,
            "before_event": True,
        }
    now = timezone.now()
    start = event.registration_start_at or event.published_at or event.created_at
    effective_end = min(now, event.end_at)
    elapsed_days = max((effective_end - start).total_seconds() / 86400, 1 / 24)
    velocity = active_access / elapsed_days
    if velocity <= 0:
        return None
    predicted = now + timedelta(days=remaining / velocity)
    return {
        "state": "forecast",
        "remaining": remaining,
        "tickets_per_day": round(velocity, 1),
        "predicted_sellout_at": predicted,
        "before_event": predicted < event.start_at,
    }


def build_event_analytics(event, user, *, days=30):
    """Event dashboard vocabulary backed only by canonical operational facts."""
    core = activity_summary(event.activity)
    access = core["access"]
    commerce = core["commerce"]
    payment = core["payment"]
    capacity = core["capacity"]

    waitlist = TicketWaitlistEntry.objects.filter(ticket_type__event=event)
    transfers = TicketTransfer.objects.filter(ticket__event=event)
    waitlist_total = waitlist.count()
    waitlist_waiting = waitlist.filter(status=WaitlistStatus.WAITING).count()
    waitlist_offered = waitlist.filter(status=WaitlistStatus.OFFERED).count()
    waitlist_converted = waitlist.filter(status=WaitlistStatus.CONVERTED).count()

    now = timezone.now()
    recent_start = now - timedelta(days=7)
    previous_start = now - timedelta(days=14)
    active_states = [AccessStatus.VALID, AccessStatus.USED]
    active_accesses = Access.objects.filter(activity=event.activity, status__in=active_states)
    recent_sales = active_accesses.filter(created_at__gte=recent_start).count()
    previous_sales = active_accesses.filter(created_at__gte=previous_start, created_at__lt=recent_start).count()
    if previous_sales:
        sales_velocity_change = round(((recent_sales - previous_sales) / previous_sales) * 100, 1)
    elif recent_sales:
        sales_velocity_change = 100.0
    else:
        sales_velocity_change = None

    active_count = access["active"]
    used_count = access["used"]
    financial_visible = user_can_view_event_financials(user, event)
    metrics = {
        "active_tickets": active_count,
        "used_tickets": used_count,
        "refunded_tickets": Access.objects.filter(activity=event.activity, status=AccessStatus.REVOKED).count(),
        "cancelled_tickets": Access.objects.filter(activity=event.activity, status=AccessStatus.CANCELLED).count(),
        "attendance_percent": _percent(used_count, active_count),
        "capacity_percent": capacity["utilization_rate"],
        "committed_capacity_percent": capacity["utilization_rate"],
        "remaining_capacity": capacity["available"],
        "reserved_quantity": capacity["held"],
        "orders_total": commerce["orders_total"],
        "confirmed_orders": commerce["confirmed_orders"],
        "pending_orders": commerce["pending_orders"],
        "cancelled_orders": commerce["cancelled_orders"],
        "expired_orders": commerce["expired_orders"],
        "order_conversion_percent": _percent(commerce["confirmed_orders"], commerce["orders_total"]),
        "average_tickets_per_order": round(active_count / commerce["confirmed_orders"], 2) if commerce["confirmed_orders"] else 0,
        "payment_attempts": payment["attempts"],
        "successful_payments": payment["succeeded"],
        "failed_payments": payment["failed"],
        "payment_conversion_percent": _percent(payment["succeeded"], payment["attempts"]),
        "waitlist_total": waitlist_total,
        "waitlist_waiting": waitlist_waiting,
        "waitlist_offered": waitlist_offered,
        "waitlist_converted": waitlist_converted,
        "waitlist_conversion_percent": _percent(waitlist_converted, waitlist_total),
        "transfers_total": transfers.count(),
        "transfers_pending": transfers.filter(status=TransferStatus.PENDING).count(),
        "transfers_accepted": transfers.filter(status=TransferStatus.ACCEPTED).count(),
        "recent_sales": recent_sales,
        "previous_sales": previous_sales,
        "sales_velocity_change_percent": sales_velocity_change,
        "forecast": _forecast(event, active_count, capacity["total"]),
        "financial_visible": financial_visible,
        "money_totals": payment["collected"] if financial_visible else [],
        "commercial_value": commerce["commercial_value"] if financial_visible else [],
        "journey_funnel": core["journey"],
        "access_summary": access,
        "capacity_summary": capacity,
    }
    metrics["insights"] = _build_insights(metrics, event)

    return {
        "event": {
            "id": str(event.pk),
            "slug": event.slug,
            "title": event.title,
            "status": event.status,
            "start_at": event.start_at,
            "end_at": event.end_at,
            "capacity": capacity["total"],
            "organization": event.organization.name if event.organization_id else None,
        },
        "metrics": metrics,
        "ticket_types": _ticket_type_breakdown(event),
        "sales_series": _access_series(event.activity, days),
        "scan_series": _access_use_series(event.activity),
        "generated_at": timezone.now(),
        "canonical_source": True,
    }
