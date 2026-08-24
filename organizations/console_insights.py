from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.utils import timezone

from access.models import AccessStatus
from activities.models import Occurrence
from automation.models import AutomationExecution, DomainAutomationExecutionStatus
from commerce.models import CommerceOrderStatus
from journeys.models import JourneyRequest, RequestStatus
from operations.models import IncidentStatus
from payments.models import PaymentStatus

from .console_selectors import (
    access_uses_for_console,
    accesses_for_console,
    automation_rules_for_console,
    capacity_for_console,
    incidents_for_console,
    orders_for_console,
    payments_for_console,
    requests_for_console,
)


def _visible_modules(context):
    return {item["key"] for group in context.navigation_groups for item in group["items"]}


def _activity_ids(context):
    if context.activity_ids is not None:
        return context.activity_ids
    return context.space.activities.values_list("id", flat=True)


def _percentage(numerator, denominator):
    if not denominator:
        return None
    return round((numerator / denominator) * 100, 1)


def analytics_insights(context):
    """Strategic Space summary derived only from canonical domain records.

    Conversion is deliberately explicit and non-financial: access utilisation is
    `Access(status=USED) / all issued Access` for the caller's authorized scope.
    A zero denominator returns None rather than a misleading 0% conversion.
    """
    visible = _visible_modules(context)
    ids = _activity_ids(context)
    result = {
        "activities": None,
        "occurrences": None,
        "journeys": None,
        "requests": None,
        "accesses": None,
        "used_accesses": None,
        "access_conversion": None,
        "capacity": None,
        "orders": None,
        "payments": None,
        "revenue_by_currency": [],
    }

    if "activities" in visible or "analytics" in visible:
        result["activities"] = context.space.activities.filter(pk__in=ids).count()
        result["occurrences"] = Occurrence.objects.filter(activity_id__in=ids).count()

    if "requests" in visible:
        requests = requests_for_console(context)
        result["requests"] = requests.count()
        result["journeys"] = requests.values("journey_id").distinct().count()

    if "access" in visible:
        accesses = accesses_for_console(context)
        result["accesses"] = accesses.count()
        result["used_accesses"] = accesses.filter(status=AccessStatus.USED).count()
        result["access_conversion"] = _percentage(result["used_accesses"], result["accesses"])

    if "offers" in visible:
        pools = capacity_for_console(context)
        finite = [pool.console_availability for pool in pools if not pool.console_availability.unlimited]
        if finite:
            total = sum((row.total or 0) for row in finite)
            available = sum((row.available or 0) for row in finite)
            result["capacity"] = {
                "total": total,
                "available": available,
                "consumed": max(total - available, 0),
            }

    if "orders" in visible:
        result["orders"] = orders_for_console(context).count()

    if "payments" in visible and context.can_view_finance:
        payments = payments_for_console(context)
        result["payments"] = payments.count()
        result["revenue_by_currency"] = list(
            payments.filter(status=PaymentStatus.SUCCEEDED)
            .values("currency")
            .annotate(total=Sum("amount"), count=Count("id"))
            .order_by("currency")
        )

    return result


def payments_insights(context):
    """Operational payment totals grouped by real Payment statuses and currency."""
    payments = payments_for_console(context)
    rows = list(
        payments.values("currency", "status")
        .annotate(total=Sum("amount"), count=Count("id"))
        .order_by("currency", "status")
    )
    grouped = defaultdict(lambda: {
        "currency": "",
        "received": Decimal("0.00"),
        "pending": Decimal("0.00"),
        "failed": Decimal("0.00"),
        "refunded": Decimal("0.00"),
        "received_count": 0,
        "pending_count": 0,
        "failed_count": 0,
        "refunded_count": 0,
    })
    for row in rows:
        bucket = grouped[row["currency"]]
        bucket["currency"] = row["currency"]
        amount = row["total"] or Decimal("0.00")
        status = row["status"]
        if status == PaymentStatus.SUCCEEDED:
            key = "received"
        elif status in {PaymentStatus.PENDING, PaymentStatus.PROCESSING}:
            key = "pending"
        elif status in {PaymentStatus.FAILED, PaymentStatus.CANCELLED}:
            key = "failed"
        elif status == PaymentStatus.REFUNDED:
            key = "refunded"
        else:
            continue
        bucket[key] += amount
        bucket[f"{key}_count"] += row["count"]
    return [grouped[currency] for currency in sorted(grouped)]


def operations_insights(context):
    """Local Space operating snapshot. Platform operations remain separate."""
    visible = _visible_modules(context)
    incidents = incidents_for_console(context)
    open_incidents = incidents.exclude(status__in={IncidentStatus.RESOLVED, IncidentStatus.DISMISSED})
    result = {
        "open_incidents": open_incidents.count(),
        "pending_requests": None,
        "valid_accesses": None,
        "used_accesses": None,
        "recent_scans": None,
        "upcoming_occurrences": Occurrence.objects.filter(
            activity_id__in=_activity_ids(context), start_at__gte=timezone.now()
        ).count(),
        "critical_capacity": [],
        "failed_automations": None,
    }
    if "requests" in visible:
        result["pending_requests"] = requests_for_console(context).filter(status=RequestStatus.PENDING).count()
    if "access" in visible or "control" in visible:
        accesses = accesses_for_console(context)
        result["valid_accesses"] = accesses.filter(status=AccessStatus.VALID).count()
        result["used_accesses"] = accesses.filter(status=AccessStatus.USED).count()
        result["recent_scans"] = access_uses_for_console(context).filter(used_at__gte=timezone.now() - timezone.timedelta(hours=24)).count()
    if "offers" in visible:
        for pool in capacity_for_console(context):
            availability = pool.console_availability
            if availability.unlimited or not availability.total:
                continue
            if availability.available / availability.total <= 0.15:
                result["critical_capacity"].append(pool)
    if "automation" in visible:
        executions = AutomationExecution.objects.filter(rule__space=context.space)
        if context.activity_ids is not None:
            executions = executions.filter(Q(rule__activity_id__in=context.activity_ids) | Q(rule__activity__isnull=True))
        result["failed_automations"] = executions.filter(status=DomainAutomationExecutionStatus.FAILED).count()
    return result


def automation_rules_insights(context):
    """Attach a safe, presentation-only latest execution to visible rules."""
    rules = list(automation_rules_for_console(context))
    for rule in rules:
        executions = list(rule.executions.all())
        rule.console_last_execution = max(executions, key=lambda item: item.created_at) if executions else None
    return rules
