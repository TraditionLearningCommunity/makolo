from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone

from events.models import EventStatus
from organizations.models import OrganizationMembership
from organizations.permissions import FINANCE_ROLES
from payments.models import Payment, PaymentStatus, Refund, RefundStatus
from scanner.models import ScanLog, ScanResult
from tickets.models import (
    Ticket,
    TicketOrder,
    TicketOrderStatus,
    TicketStatus,
    TicketTransfer,
    TicketType,
    TicketWaitlistEntry,
    TransferStatus,
    WaitlistStatus,
)

from .permissions import user_can_view_event_financials
from .selectors import get_analytics_events


ACTIVE_TICKET_STATUSES = [TicketStatus.VALID, TicketStatus.USED]
SUCCESS_PAYMENT_STATUSES = [PaymentStatus.SUCCEEDED, PaymentStatus.REFUNDED]


def _percent(numerator, denominator):
    if not denominator:
        return None
    return round((numerator / denominator) * 100, 1)


def _money_totals(event):
    gross_rows = (
        Payment.objects.filter(
            order__event=event,
            status__in=SUCCESS_PAYMENT_STATUSES,
        )
        .values("currency")
        .annotate(total=Sum("amount"))
    )
    refund_rows = (
        Refund.objects.filter(
            payment__order__event=event,
            status=RefundStatus.SUCCEEDED,
        )
        .values("currency")
        .annotate(total=Sum("amount"))
    )
    gross = {row["currency"]: row["total"] or Decimal("0") for row in gross_rows}
    refunds = {row["currency"]: row["total"] or Decimal("0") for row in refund_rows}
    currencies = sorted(set(gross) | set(refunds))
    return [
        {
            "currency": currency,
            "gross": gross.get(currency, Decimal("0")),
            "refunds": refunds.get(currency, Decimal("0")),
            "net": gross.get(currency, Decimal("0")) - refunds.get(currency, Decimal("0")),
        }
        for currency in currencies
    ]


def _sales_series(event, days):
    days = min(max(int(days or 30), 7), 90)
    today = timezone.localdate()
    start_day = today - timedelta(days=days - 1)
    rows = (
        Ticket.objects.filter(
            event=event,
            status__in=ACTIVE_TICKET_STATUSES,
            issued_at__date__gte=start_day,
        )
        .annotate(day=TruncDate("issued_at"))
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


def _scan_series(event):
    rows = (
        ScanLog.objects.filter(event=event, result=ScanResult.ACCEPTED)
        .annotate(hour=TruncHour("scanned_at"))
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


def _ticket_type_breakdown(event):
    rows = TicketType.objects.filter(event=event).annotate(
        active_count=Count(
            "tickets",
            filter=Q(tickets__status__in=ACTIVE_TICKET_STATUSES),
            distinct=True,
        ),
        used_count=Count(
            "tickets",
            filter=Q(tickets__status=TicketStatus.USED),
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
        sell_through = _percent(row.active_count, row.quantity_total) if row.quantity_total else None
        result.append(
            {
                "id": str(row.pk),
                "name": row.name,
                "price": row.price,
                "currency": row.currency,
                "quantity_total": row.quantity_total,
                "reserved_quantity": row.reserved_quantity,
                "issued_quantity": row.issued_quantity,
                "active_count": row.active_count,
                "used_count": row.used_count,
                "waiting_count": row.waiting_count,
                "available_quantity": available,
                "sell_through_percent": sell_through,
            }
        )
    return result


def _forecast(event, active_tickets):
    if not event.capacity or active_tickets <= 0 or event.status != EventStatus.PUBLISHED:
        return None
    remaining = max(event.capacity - active_tickets, 0)
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
    tickets_per_day = active_tickets / elapsed_days
    if tickets_per_day <= 0:
        return None
    days_to_sellout = remaining / tickets_per_day
    predicted = now + timedelta(days=days_to_sellout)
    return {
        "state": "forecast",
        "remaining": remaining,
        "tickets_per_day": round(tickets_per_day, 1),
        "predicted_sellout_at": predicted,
        "before_event": predicted < event.start_at,
    }


def _build_insights(metrics, event):
    insights = []
    capacity_percent = metrics["capacity_percent"]
    if capacity_percent is not None and capacity_percent >= 90:
        insights.append(
            {
                "level": "warning",
                "title": "Capacité presque atteinte",
                "body": f"{capacity_percent}% de la capacité est déjà occupée par des billets actifs.",
                "action": "Surveillez la file d’attente et la capacité opérationnelle.",
            }
        )

    if metrics["waitlist_waiting"] > 0:
        insights.append(
            {
                "level": "info",
                "title": "Demande non servie",
                "body": f"{metrics['waitlist_waiting']} personne(s) attendent encore une place.",
                "action": "Vérifiez les réservations expirantes ou augmentez la capacité si cela est possible.",
            }
        )

    payment_conversion = metrics["payment_conversion_percent"]
    if metrics["payment_attempts"] >= 5 and payment_conversion is not None and payment_conversion < 70:
        insights.append(
            {
                "level": "critical",
                "title": "Friction de paiement",
                "body": f"Seulement {payment_conversion}% des tentatives de paiement aboutissent.",
                "action": "Contrôlez les échecs par méthode et fournisseur avant une campagne supplémentaire.",
            }
        )

    velocity = metrics["sales_velocity_change_percent"]
    if velocity is not None and velocity >= 25:
        insights.append(
            {
                "level": "positive",
                "title": "Accélération des ventes",
                "body": f"Le rythme des billets émis progresse de {velocity}% par rapport aux 7 jours précédents.",
                "action": "Préparez la capacité d’accueil et le contrôle d’accès si cette tendance continue.",
            }
        )
    elif velocity is not None and velocity <= -30 and event.start_at > timezone.now():
        insights.append(
            {
                "level": "warning",
                "title": "Ralentissement des ventes",
                "body": f"Le rythme récent recule de {abs(velocity)}% par rapport aux 7 jours précédents.",
                "action": "Analysez les canaux d’acquisition, le prix et la fenêtre de communication.",
            }
        )

    if event.start_at <= timezone.now() and metrics["active_tickets"] >= 10:
        attendance = metrics["attendance_percent"]
        if attendance is not None and attendance < 70:
            insights.append(
                {
                    "level": "warning",
                    "title": "Présence inférieure aux billets émis",
                    "body": f"{attendance}% des billets actifs ont été scannés pour le moment.",
                    "action": "Mesurez le no-show et comparez-le aux prochaines éditions.",
                }
            )

    forecast = metrics["forecast"]
    if forecast and forecast.get("state") == "forecast" and forecast.get("before_event"):
        predicted = timezone.localtime(forecast["predicted_sellout_at"])
        insights.append(
            {
                "level": "positive",
                "title": "Risque de sold-out avant l’événement",
                "body": f"Au rythme actuel, la capacité pourrait être atteinte vers le {predicted:%d/%m à %H:%M}.",
                "action": "Préparez la waitlist et évitez de promettre une capacité non disponible.",
            }
        )

    if metrics["pending_orders"] > 0:
        insights.append(
            {
                "level": "info",
                "title": "Stock temporairement réservé",
                "body": f"{metrics['pending_orders']} commande(s) sont encore en attente de confirmation.",
                "action": "Autopilot libérera automatiquement les réservations expirées.",
            }
        )

    return insights[:6]


def build_event_analytics(event, user, *, days=30):
    tickets = Ticket.objects.filter(event=event)
    active_tickets = tickets.filter(status__in=ACTIVE_TICKET_STATUSES).count()
    used_tickets = tickets.filter(status=TicketStatus.USED).count()
    refunded_tickets = tickets.filter(status=TicketStatus.REFUNDED).count()
    cancelled_tickets = tickets.filter(status=TicketStatus.CANCELLED).count()

    orders = TicketOrder.objects.filter(event=event)
    orders_total = orders.count()
    confirmed_orders = orders.filter(status=TicketOrderStatus.CONFIRMED).count()
    pending_orders = orders.filter(status=TicketOrderStatus.PENDING).count()
    cancelled_orders = orders.filter(status=TicketOrderStatus.CANCELLED).count()
    expired_orders = orders.filter(status=TicketOrderStatus.EXPIRED).count()

    payments = Payment.objects.filter(order__event=event)
    payment_attempts = payments.count()
    successful_payments = payments.filter(status__in=SUCCESS_PAYMENT_STATUSES).count()
    failed_payments = payments.filter(status=PaymentStatus.FAILED).count()

    waitlist = TicketWaitlistEntry.objects.filter(ticket_type__event=event)
    waitlist_total = waitlist.count()
    waitlist_waiting = waitlist.filter(status=WaitlistStatus.WAITING).count()
    waitlist_offered = waitlist.filter(status=WaitlistStatus.OFFERED).count()
    waitlist_converted = waitlist.filter(status=WaitlistStatus.CONVERTED).count()

    transfers = TicketTransfer.objects.filter(ticket__event=event)
    transfers_total = transfers.count()
    transfers_pending = transfers.filter(status=TransferStatus.PENDING).count()
    transfers_accepted = transfers.filter(status=TransferStatus.ACCEPTED).count()

    now = timezone.now()
    recent_start = now - timedelta(days=7)
    previous_start = now - timedelta(days=14)
    recent_sales = tickets.filter(
        status__in=ACTIVE_TICKET_STATUSES,
        issued_at__gte=recent_start,
    ).count()
    previous_sales = tickets.filter(
        status__in=ACTIVE_TICKET_STATUSES,
        issued_at__gte=previous_start,
        issued_at__lt=recent_start,
    ).count()
    if previous_sales:
        sales_velocity_change = round(((recent_sales - previous_sales) / previous_sales) * 100, 1)
    elif recent_sales:
        sales_velocity_change = 100.0
    else:
        sales_velocity_change = None

    reserved_quantity = sum(
        row["reserved_quantity"]
        for row in TicketType.objects.filter(event=event).values("reserved_quantity")
    )
    capacity_percent = _percent(active_tickets, event.capacity) if event.capacity else None
    committed_capacity_percent = (
        _percent(active_tickets + reserved_quantity, event.capacity) if event.capacity else None
    )

    financial_visible = user_can_view_event_financials(user, event)
    metrics = {
        "active_tickets": active_tickets,
        "used_tickets": used_tickets,
        "refunded_tickets": refunded_tickets,
        "cancelled_tickets": cancelled_tickets,
        "attendance_percent": _percent(used_tickets, active_tickets),
        "capacity_percent": capacity_percent,
        "committed_capacity_percent": committed_capacity_percent,
        "remaining_capacity": max(event.capacity - active_tickets - reserved_quantity, 0) if event.capacity else None,
        "reserved_quantity": reserved_quantity,
        "orders_total": orders_total,
        "confirmed_orders": confirmed_orders,
        "pending_orders": pending_orders,
        "cancelled_orders": cancelled_orders,
        "expired_orders": expired_orders,
        "order_conversion_percent": _percent(confirmed_orders, orders_total),
        "average_tickets_per_order": round(active_tickets / confirmed_orders, 2) if confirmed_orders else 0,
        "payment_attempts": payment_attempts,
        "successful_payments": successful_payments,
        "failed_payments": failed_payments,
        "payment_conversion_percent": _percent(successful_payments, payment_attempts),
        "waitlist_total": waitlist_total,
        "waitlist_waiting": waitlist_waiting,
        "waitlist_offered": waitlist_offered,
        "waitlist_converted": waitlist_converted,
        "waitlist_conversion_percent": _percent(waitlist_converted, waitlist_total),
        "transfers_total": transfers_total,
        "transfers_pending": transfers_pending,
        "transfers_accepted": transfers_accepted,
        "recent_sales": recent_sales,
        "previous_sales": previous_sales,
        "sales_velocity_change_percent": sales_velocity_change,
        "forecast": _forecast(event, active_tickets),
        "financial_visible": financial_visible,
        "money_totals": _money_totals(event) if financial_visible else [],
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
            "capacity": event.capacity,
            "organization": event.organization.name if event.organization_id else None,
        },
        "metrics": metrics,
        "ticket_types": _ticket_type_breakdown(event),
        "sales_series": _sales_series(event, days),
        "scan_series": _scan_series(event),
        "generated_at": timezone.now(),
    }


def build_portfolio_analytics(user):
    events = list(get_analytics_events(user).order_by("-start_at")[:40])
    event_ids = [event.pk for event in events]
    now = timezone.now()

    active_by_event = defaultdict(int)
    for row in (
        Ticket.objects.filter(event_id__in=event_ids, status__in=ACTIVE_TICKET_STATUSES)
        .values("event_id")
        .annotate(total=Count("id"))
    ):
        active_by_event[row["event_id"]] = row["total"]

    used_by_event = defaultdict(int)
    for row in (
        Ticket.objects.filter(event_id__in=event_ids, status=TicketStatus.USED)
        .values("event_id")
        .annotate(total=Count("id"))
    ):
        used_by_event[row["event_id"]] = row["total"]

    confirmed_by_event = defaultdict(int)
    for row in (
        TicketOrder.objects.filter(event_id__in=event_ids, status=TicketOrderStatus.CONFIRMED)
        .values("event_id")
        .annotate(total=Count("id"))
    ):
        confirmed_by_event[row["event_id"]] = row["total"]

    waiting_by_event = defaultdict(int)
    for row in (
        TicketWaitlistEntry.objects.filter(
            ticket_type__event_id__in=event_ids,
            status=WaitlistStatus.WAITING,
        )
        .values("ticket_type__event_id")
        .annotate(total=Count("id"))
    ):
        waiting_by_event[row["ticket_type__event_id"]] = row["total"]

    if user.is_staff:
        financial_event_ids = set(event_ids)
    else:
        finance_org_ids = set(
            OrganizationMembership.objects.filter(
                user=user,
                is_active=True,
                role__in=FINANCE_ROLES,
            ).values_list("organization_id", flat=True)
        )
        financial_event_ids = {
            event.pk
            for event in events
            if (event.organization_id and event.organization_id in finance_org_ids)
            or (not event.organization_id and user_can_view_event_financials(user, event))
        }

    gross_by_event = defaultdict(lambda: defaultdict(lambda: Decimal("0")))
    for row in (
        Payment.objects.filter(
            order__event_id__in=financial_event_ids,
            status__in=SUCCESS_PAYMENT_STATUSES,
        )
        .values("order__event_id", "currency")
        .annotate(total=Sum("amount"))
    ):
        gross_by_event[row["order__event_id"]][row["currency"]] = row["total"] or Decimal("0")

    refunds_by_event = defaultdict(lambda: defaultdict(lambda: Decimal("0")))
    for row in (
        Refund.objects.filter(
            payment__order__event_id__in=financial_event_ids,
            status=RefundStatus.SUCCEEDED,
        )
        .values("payment__order__event_id", "currency")
        .annotate(total=Sum("amount"))
    ):
        refunds_by_event[row["payment__order__event_id"]][row["currency"]] = row["total"] or Decimal("0")

    cards = []
    portfolio_money = defaultdict(lambda: {"gross": Decimal("0"), "refunds": Decimal("0")})
    for event in events:
        active = active_by_event[event.pk]
        used = used_by_event[event.pk]
        financial_visible = event.pk in financial_event_ids
        money = []
        if financial_visible:
            currencies = sorted(set(gross_by_event[event.pk]) | set(refunds_by_event[event.pk]))
            for currency in currencies:
                gross = gross_by_event[event.pk][currency]
                refunds = refunds_by_event[event.pk][currency]
                money.append({"currency": currency, "gross": gross, "refunds": refunds, "net": gross - refunds})
                portfolio_money[currency]["gross"] += gross
                portfolio_money[currency]["refunds"] += refunds
        cards.append(
            {
                "event": event,
                "active_tickets": active,
                "used_tickets": used,
                "attendance_percent": _percent(used, active),
                "capacity_percent": _percent(active, event.capacity) if event.capacity else None,
                "confirmed_orders": confirmed_by_event[event.pk],
                "waitlist_waiting": waiting_by_event[event.pk],
                "financial_visible": financial_visible,
                "money_totals": money,
            }
        )

    money_totals = [
        {
            "currency": currency,
            "gross": values["gross"],
            "refunds": values["refunds"],
            "net": values["gross"] - values["refunds"],
        }
        for currency, values in sorted(portfolio_money.items())
    ]

    return {
        "events_count": len(events),
        "published_count": sum(event.status == EventStatus.PUBLISHED for event in events),
        "upcoming_count": sum(event.start_at > now and event.status == EventStatus.PUBLISHED for event in events),
        "active_tickets": sum(active_by_event.values()),
        "used_tickets": sum(used_by_event.values()),
        "attendance_percent": _percent(sum(used_by_event.values()), sum(active_by_event.values())),
        "confirmed_orders": sum(confirmed_by_event.values()),
        "waitlist_waiting": sum(waiting_by_event.values()),
        "money_totals": money_totals,
        "event_cards": cards,
        "generated_at": timezone.now(),
    }
