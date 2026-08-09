from datetime import timedelta

from django.db.models import Sum
from django.utils import timezone

from crm.services import process_due_campaigns
from events.models import Event, EventStatus
from loyalty.services import expire_due_memberships
from notifications.models import (
    DeliveryStatus,
    NotificationCategory,
    NotificationDelivery,
    NotificationKind,
)
from notifications.services import create_notification, dispatch_pending
from organizations.models import OrganizationRole
from tickets.models import Ticket, TicketOrder, TicketOrderStatus, TicketStatus, TicketType
from tickets.services import expire_due_ticket_transfers, expire_order, promote_open_waitlists

from .models import AutomationRun, AutomationRunStatus, EventAutomationPolicy


REMINDER_RULES = (
    ("reminder_7d_enabled", "event-reminder-7d", timedelta(days=7), timedelta(hours=6), "Dans 7 jours"),
    ("reminder_24h_enabled", "event-reminder-24h", timedelta(hours=24), timedelta(hours=3), "Demain"),
    ("reminder_2h_enabled", "event-reminder-2h", timedelta(hours=2), timedelta(minutes=30), "Dans 2 heures"),
)


def ensure_policy(event: Event) -> EventAutomationPolicy:
    policy, _ = EventAutomationPolicy.objects.get_or_create(event=event)
    return policy


def _record_once(*, event, rule_key, dedup_key, summary="", payload=None, status=AutomationRunStatus.SUCCESS):
    return AutomationRun.objects.get_or_create(
        dedup_key=dedup_key,
        defaults={"event": event, "rule_key": rule_key, "summary": summary[:255], "payload": payload or {}, "status": status},
    )


def _event_team_recipient_objects(event):
    if event.organization_id:
        return [
            membership.user
            for membership in event.organization.memberships.filter(
                is_active=True,
                role__in=[OrganizationRole.OWNER, OrganizationRole.ADMIN, OrganizationRole.EVENT_MANAGER, OrganizationRole.MARKETING],
            ).select_related("user")
        ]
    return [event.organizer] if event.organizer_id else []


def _notify_event_team(event, *, title, message, dedup_prefix, category=NotificationCategory.EVENT):
    count = 0
    for user in _event_team_recipient_objects(event):
        create_notification(
            recipient=user,
            kind=NotificationKind.SYSTEM,
            category=category,
            title=title,
            message=message,
            action_url=f"/events/{event.slug}/",
            dedup_key=f"{dedup_prefix}:{event.pk}:{user.pk}",
            metadata={"event_id": str(event.pk)},
        )
        count += 1
    return count


def _run_reminders(event, policy, now):
    created = 0
    for field_name, rule_key, offset, grace, label in REMINDER_RULES:
        if not getattr(policy, field_name):
            continue
        due_at = event.start_at - offset
        if now < due_at or now > due_at + grace or now >= event.start_at:
            continue
        tickets = Ticket.objects.filter(event=event, status=TicketStatus.VALID, owner__isnull=False).select_related("owner").order_by("owner_id")
        seen = set()
        for ticket in tickets:
            if ticket.owner_id in seen:
                continue
            seen.add(ticket.owner_id)
            dedup_key = f"autopilot:{rule_key}:{event.pk}:{ticket.owner_id}"
            run, run_created = _record_once(
                event=event,
                rule_key=rule_key,
                dedup_key=dedup_key,
                summary=f"Rappel {label} pour {ticket.owner.email}",
                payload={"user_id": str(ticket.owner_id)},
            )
            if not run_created:
                continue
            create_notification(
                recipient=ticket.owner,
                kind=NotificationKind.EVENT_REMINDER,
                category=NotificationCategory.EVENT,
                title=f"{label} — {event.title}",
                message=f"« {event.title} » commence le {timezone.localtime(event.start_at).strftime('%d/%m/%Y à %H:%M')}. Votre billet et son QR code sont disponibles dans Makolo.",
                action_url=f"/events/{event.slug}/",
                dedup_key=f"notification:{dedup_key}",
                metadata={"event_id": str(event.pk), "automation_run_id": str(run.pk)},
            )
            created += 1
    return created


def _run_capacity_alert(event, policy):
    if not policy.capacity_alerts_enabled or not event.capacity:
        return 0
    committed = TicketType.objects.filter(event=event).aggregate(reserved=Sum("reserved_quantity"), issued=Sum("issued_quantity"))
    total = (committed["reserved"] or 0) + (committed["issued"] or 0)
    percent = int((total / event.capacity) * 100)
    if percent < policy.capacity_alert_percent:
        return 0
    dedup = f"autopilot:capacity:{policy.capacity_alert_percent}:{event.pk}"
    _, created = _record_once(
        event=event,
        rule_key="capacity-alert",
        dedup_key=dedup,
        summary=f"Capacité à {percent}%",
        payload={"percent": percent, "committed": total, "capacity": event.capacity},
    )
    if not created:
        return 0
    return _notify_event_team(
        event,
        title=f"{event.title} atteint {percent}% de capacité",
        message=f"{total} place(s) sont réservées ou émises sur {event.capacity}. Makolo Autopilot continuera à surveiller le remplissage.",
        dedup_prefix=f"notification:{dedup}",
    )


def _run_low_stock_alerts(event, policy):
    if not policy.low_stock_alerts_enabled:
        return 0
    alerts = 0
    for ticket_type in TicketType.objects.filter(event=event, is_active=True):
        available = ticket_type.available_quantity
        if available is None or available > policy.low_stock_threshold:
            continue
        dedup = f"autopilot:low-stock:{ticket_type.pk}:{policy.low_stock_threshold}"
        _, created = _record_once(
            event=event,
            rule_key="low-stock",
            dedup_key=dedup,
            summary=f"Stock faible {ticket_type.name}: {available}",
            payload={"ticket_type_id": str(ticket_type.pk), "available": available},
        )
        if not created:
            continue
        alerts += _notify_event_team(
            event,
            title=f"Stock faible — {ticket_type.name}",
            message=f"Il ne reste que {available} billet(s) « {ticket_type.name} » pour {event.title}.",
            dedup_prefix=f"notification:{dedup}",
        )
    return alerts


def _auto_close_sales(event, policy, now):
    if not policy.auto_close_sales_at_start or now < event.start_at:
        return 0
    dedup = f"autopilot:close-sales:{event.pk}"
    _, created = _record_once(event=event, rule_key="close-sales", dedup_key=dedup, summary="Ventes fermées automatiquement au début de l'événement")
    if not created:
        return 0
    return TicketType.objects.filter(event=event, is_active=True).update(is_active=False, updated_at=now)


def _auto_complete(event, policy, now):
    if not policy.auto_complete_event or event.status != EventStatus.PUBLISHED or now < event.end_at:
        return 0
    dedup = f"autopilot:complete-event:{event.pk}"
    _, created = _record_once(event=event, rule_key="complete-event", dedup_key=dedup, summary="Événement terminé automatiquement")
    if not created:
        return 0
    Event.objects.filter(pk=event.pk, status=EventStatus.PUBLISHED).update(status=EventStatus.COMPLETED, updated_at=now)
    event.status = EventStatus.COMPLETED
    return 1


def _post_event_followup(event, policy, now):
    if not policy.post_event_followup_enabled or now < event.end_at:
        return 0
    users = Ticket.objects.filter(event=event, owner__isnull=False).exclude(status=TicketStatus.CANCELLED).select_related("owner").order_by("owner_id")
    created = 0
    seen = set()
    for ticket in users:
        if ticket.owner_id in seen:
            continue
        seen.add(ticket.owner_id)
        dedup = f"autopilot:followup:{event.pk}:{ticket.owner_id}"
        _, run_created = _record_once(event=event, rule_key="post-event-followup", dedup_key=dedup, summary=f"Suivi post-événement pour {ticket.owner.email}")
        if not run_created:
            continue
        create_notification(
            recipient=ticket.owner,
            kind=NotificationKind.SYSTEM,
            category=NotificationCategory.EVENT,
            title=f"Merci d'avoir participé à {event.title}",
            message="Merci d'avoir utilisé Makolo. Votre participation est enregistrée. Les avis et recommandations personnalisées pourront s'appuyer sur cet historique sans exposer vos données à l'organisateur.",
            action_url=f"/events/{event.slug}/",
            dedup_key=f"notification:{dedup}",
            metadata={"event_id": str(event.pk)},
        )
        created += 1
    return created


def expire_due_orders(*, now=None, limit=200):
    now = now or timezone.now()
    orders = list(TicketOrder.objects.filter(status=TicketOrderStatus.PENDING, expires_at__isnull=False, expires_at__lte=now).order_by("expires_at")[:limit])
    count = 0
    for order in orders:
        expire_order(order=order)
        count += 1
    return count


def recover_stale_notification_deliveries(*, now=None, stale_minutes=15):
    now = now or timezone.now()
    cutoff = now - timedelta(minutes=stale_minutes)
    return NotificationDelivery.objects.filter(status=DeliveryStatus.PROCESSING, updated_at__lt=cutoff).update(
        status=DeliveryStatus.QUEUED,
        scheduled_for=now,
        last_error="Reprise automatique après interruption du worker.",
        updated_at=now,
    )


def run_autopilot_cycle(*, now=None, delivery_limit=100):
    now = now or timezone.now()
    stats = {
        "expired_orders": expire_due_orders(now=now),
        "expired_transfers": expire_due_ticket_transfers(now=now),
        "expired_memberships": expire_due_memberships(now=now),
        "waitlist_promotions": promote_open_waitlists(now=now),
        "recovered_deliveries": recover_stale_notification_deliveries(now=now),
        "reminders": 0,
        "capacity_alerts": 0,
        "low_stock_alerts": 0,
        "sales_closed": 0,
        "events_completed": 0,
        "followups": 0,
    }
    events = Event.objects.filter(status__in=[EventStatus.PUBLISHED, EventStatus.COMPLETED]).select_related("organizer", "organization").prefetch_related("organization__memberships__user")
    for event in events:
        policy = ensure_policy(event)
        if not policy.is_active:
            continue
        if event.status == EventStatus.PUBLISHED:
            stats["reminders"] += _run_reminders(event, policy, now)
            stats["capacity_alerts"] += _run_capacity_alert(event, policy)
            stats["low_stock_alerts"] += _run_low_stock_alerts(event, policy)
            stats["sales_closed"] += _auto_close_sales(event, policy, now)
            stats["events_completed"] += _auto_complete(event, policy, now)
        if event.status == EventStatus.COMPLETED or now >= event.end_at:
            stats["followups"] += _post_event_followup(event, policy, now)
    stats["crm_campaigns"] = process_due_campaigns(now=now, recipient_limit=delivery_limit)
    stats["deliveries"] = dispatch_pending(limit=delivery_limit)
    return stats
