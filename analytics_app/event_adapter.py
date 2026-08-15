from datetime import timedelta

from django.db.models import Count
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone

from access.models import Access, AccessStatus, AccessUse, AccessUseResult

from .canonical import activity_summary
from .services import (
    _build_insights,
    _forecast,
    _percent,
    build_event_analytics as build_legacy_event_analytics,
)


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
    series = []
    for offset in range(days):
        day = start_day + timedelta(days=offset)
        quantity = values.get(day, 0)
        series.append(
            {
                "date": day.isoformat(),
                "label": day.strftime("%d/%m"),
                "quantity": quantity,
                "bar_width": round((quantity / maximum) * 100, 1) if maximum else 0,
            }
        )
    return series


def _access_use_series(activity):
    rows = (
        AccessUse.objects.filter(access__activity=activity, result=AccessUseResult.ACCEPTED)
        .annotate(hour=TruncHour("used_at"))
        .values("hour")
        .annotate(quantity=Count("id"))
        .order_by("hour")
    )
    rows = list(rows)
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


def build_event_analytics(event, user, *, days=30):
    """Keep Event vocabulary while sourcing shared KPIs from canonical models."""
    data = build_legacy_event_analytics(event, user, days=days)
    if not event.activity_id:
        return data

    core = activity_summary(event.activity)
    access = core["access"]
    commerce = core["commerce"]
    payment = core["payment"]
    capacity = core["capacity"]
    metrics = data["metrics"]

    active_access = access["active"]
    used_access = access["used"]
    metrics.update(
        {
            "active_tickets": active_access,
            "used_tickets": used_access,
            "attendance_percent": _percent(used_access, active_access),
            "orders_total": commerce["orders_total"],
            "confirmed_orders": commerce["confirmed_orders"],
            "pending_orders": commerce["pending_orders"],
            "cancelled_orders": commerce["cancelled_orders"],
            "expired_orders": commerce["expired_orders"],
            "order_conversion_percent": _percent(commerce["confirmed_orders"], commerce["orders_total"]),
            "average_tickets_per_order": (
                round(active_access / commerce["confirmed_orders"], 2)
                if commerce["confirmed_orders"] else 0
            ),
            "payment_attempts": payment["attempts"],
            "successful_payments": payment["succeeded"],
            "failed_payments": payment["failed"],
            "payment_conversion_percent": _percent(payment["succeeded"], payment["attempts"]),
            "reserved_quantity": capacity["held"],
            "remaining_capacity": capacity["available"],
            "capacity_percent": capacity["utilization_rate"],
            "committed_capacity_percent": capacity["utilization_rate"],
            "forecast": _forecast(event, active_access),
            "money_totals": payment["collected"] if metrics["financial_visible"] else [],
            "commercial_value": commerce["commercial_value"] if metrics["financial_visible"] else [],
            "journey_funnel": core["journey"],
            "access_summary": access,
            "capacity_summary": capacity,
        }
    )
    metrics["insights"] = _build_insights(metrics, event)
    data["sales_series"] = _access_series(event.activity, days)
    data["scan_series"] = _access_use_series(event.activity)
    data["canonical_source"] = True
    return data
