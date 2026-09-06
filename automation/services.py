from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Q, Sum
from django.utils import timezone

from activities.models import ActivityStatus, OccurrenceStatus
from activities.services import complete_occurrence, update_activity_common
from commerce.models import OfferStatus
from commerce.services import update_offer
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


User = get_user_model()
COMPLETED_EVENT_CATCHUP_DAYS = 30
REMINDER_RULES = (
    ("reminder_7d_enabled", "event-reminder-7d", timedelta(days=7), timedelta(hours=6), "Dans 7 jours"),
    ("reminder_24h_enabled", "event-reminder-24h", timedelta(hours=24), timedelta(hours=3), "Demain"),
    ("reminder_2h_enabled", "event-reminder-2h", timedelta(hours=2), timedelta(minutes=70), "Dans 2 heures"),
)


def ensure_policy(event: Event) -> EventAutomationPolicy:
    try:
        return event.automation_policy
    except EventAutomationPolicy.DoesNotExist:
        policy, _ = EventAutomationPolicy.objects.get_or_create(event=event)
        return policy


def _record_once(*, event, rule_key, dedup_key, summary="", payload=None, status=AutomationRunStatus.SUCCESS):
    return AutomationRun.objects.get_or_create(
        dedup_key=dedup_key,
        defaults={
            "event": event,
            "rule_key": rule_key,
            "summary": summary[:255],
            "payload": payload or {},
            "status": status,
        },
    )


def _event_team_recipient_objects(event):
    if event.organization_id:
        return [
            membership.user
            for membership in event.organization.memberships.filter(
                is_active=True,
                role__in=[
                    OrganizationRole.OWNER,
                    OrganizationRole.ADMIN,
                    OrganizationRole.EVENT_MANAGER,
                    OrganizationRole.MARKETING,
                ],
            ).select_related("user")
        ]
    return [event.organizer] if event.organizer_id else []


def _event_participants(event, *, occurrence=None, include_cancelled=False):
    tickets = Ticket.objects.filter(event=event, owner__isnull=False)
    if occurrence is not None:
        tickets = tickets.filter(ticket_type__offer__occurrence=occurrence)
    if not include_cancelled:
        tickets = tickets.exclude(status=TicketStatus.CANCELLED)
    owner_ids = tickets.values_list("owner_id", flat=True).distinct()
    return User.objects.filter(pk__in=owner_ids).order_by("pk")


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


def _scheduled_occurrences(event):
    return list(
        event.activity.occurrences.filter(status=OccurrenceStatus.SCHEDULED)
        .order_by("start_date", "start_time", "id")
    )


def _run_reminders(event, policy, now):
    created = 0
    # Reminder offsets require a real instant. Date-only/all-day occurrences
    # intentionally do not produce synthetic countdowns.
    for occurrence in _scheduled_occurrences(event):
        if occurrence.start_at is None:
            continue
        for field_name, rule_key, offset, grace, label in REMINDER_RULES:
            if not getattr(policy, field_name):
                continue
            due_at = occurrence.start_at - offset
            if now < due_at or now > due_at + grace or now >= occurrence.start_at:
                continue
            for participant in _event_participants(event, occurrence=occurrence, include_cancelled=False):
                dedup_key = f"autopilot:{rule_key}:{occurrence.pk}:{participant.pk}"
                run, run_created = _record_once(
                    event=event,
                    rule_key=rule_key,
                    dedup_key=dedup_key,
                    summary=f"Rappel {label} pour {participant.email}",
                    payload={"user_id": str(participant.pk), "occurrence_id": str(occurrence.pk)},
                )
                if not run_created:
                    continue
                create_notification(
                    recipient=participant,
                    kind=NotificationKind.EVENT_REMINDER,
                    category=NotificationCategory.EVENT,
                    title=f"{label} — {event.title}",
                    message=(
                        f"« {event.title} » commence le "
                        f"{occurrence.start_at.astimezone(timezone.get_current_timezone()).strftime('%d/%m/%Y à %H:%M')}. "
                        "Votre billet et son QR code sont disponibles dans Makolo."
                    ),
                    action_url=f"/events/{event.slug}/?occurrence={occurrence.pk}",
                    dedup_key=f"notification:{dedup_key}",
                    metadata={
                        "event_id": str(event.pk),
                        "occurrence_id": str(occurrence.pk),
                        "automation_run_id": str(run.pk),
                    },
                )
                created += 1
    return created


def _run_capacity_alert(event, policy):
    # The historical event-wide percentage is only meaningful when there is one
    # concrete occurrence. Multi-date capacity remains occurrence-scoped.
    occurrences = list(event.activity.occurrences.all()[:2])
    if len(occurrences) != 1 or not policy.capacity_alerts_enabled or not event.capacity:
        return 0
    committed = TicketType.objects.filter(event=event, offer__occurrence=occurrences[0]).aggregate(
        reserved=Sum("capacity_pool__reservations__quantity", filter=Q(capacity_pool__reservations__status="held")),
        issued=Sum("capacity_pool__reservations__quantity", filter=Q(capacity_pool__reservations__status="committed")),
    )
    total = (committed["reserved"] or 0) + (committed["issued"] or 0)
    percent = int((total / event.capacity) * 100)
    if percent < policy.capacity_alert_percent:
        return 0
    dedup = f"autopilot:capacity:{policy.capacity_alert_percent}:{event.pk}:{occurrences[0].pk}"
    _, created = _record_once(
        event=event,
        rule_key="capacity-alert",
        dedup_key=dedup,
        summary=f"Capacité à {percent}%",
        payload={"percent": percent, "committed": total, "capacity": event.capacity, "occurrence_id": str(occurrences[0].pk)},
    )
    if not created:
        return 0
    return _notify_event_team(
        event,
        title=f"{event.title} atteint {percent}% de capacité",
        message=f"{total} place(s) sont retenues ou engagées sur {event.capacity}.",
        dedup_prefix=f"notification:{dedup}",
    )


def _run_low_stock_alerts(event, policy):
    if not policy.low_stock_alerts_enabled:
        return 0
    alerts = 0
    ticket_types = TicketType.objects.filter(event=event).select_related("offer__occurrence", "capacity_pool")
    for ticket_type in ticket_types:
        if not ticket_type.is_active:
            continue
        available = ticket_type.available_quantity
        if available is None or available > policy.low_stock_threshold:
            continue
        occurrence_id = ticket_type.offer.occurrence_id
        dedup = f"autopilot:low-stock:{ticket_type.pk}:{policy.low_stock_threshold}"
        _, created = _record_once(
            event=event,
            rule_key="low-stock",
            dedup_key=dedup,
            summary=f"Stock faible {ticket_type.name}: {available}",
            payload={"ticket_type_id": str(ticket_type.pk), "occurrence_id": str(occurrence_id) if occurrence_id else None, "available": available},
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
    if not policy.auto_close_sales_at_start:
        return 0
    closed = 0
    ticket_types = TicketType.objects.filter(event=event).select_related("offer__occurrence")
    for ticket_type in ticket_types:
        offer = ticket_type.offer
        occurrence = offer.occurrence
        if occurrence is None or occurrence.start_at is None or now < occurrence.start_at:
            continue
        if offer.status != OfferStatus.ACTIVE:
            continue
        dedup = f"autopilot:close-sales:{event.pk}:{occurrence.pk}:{ticket_type.pk}"
        _, created = _record_once(
            event=event,
            rule_key="close-sales",
            dedup_key=dedup,
            summary="Ventes fermées automatiquement au début de la séance",
            payload={"occurrence_id": str(occurrence.pk), "ticket_type_id": str(ticket_type.pk)},
        )
        if not created:
            continue
        update_offer(offer=offer, status=OfferStatus.INACTIVE)
        closed += 1
    return closed


def _auto_complete(event, policy, now):
    if not policy.auto_complete_event or event.status != EventStatus.PUBLISHED:
        return 0
    occurrences = list(event.activity.occurrences.all())
    if not occurrences:
        return 0
    for occurrence in occurrences:
        if occurrence.status in {OccurrenceStatus.CANCELLED, OccurrenceStatus.COMPLETED}:
            continue
        if occurrence.end_at is None or occurrence.end_at > now:
            return 0
    dedup = f"autopilot:complete-event:{event.pk}"
    _, created = _record_once(
        event=event,
        rule_key="complete-event",
        dedup_key=dedup,
        summary="Événement terminé automatiquement après sa dernière séance",
    )
    if not created:
        return 0
    for occurrence in occurrences:
        if occurrence.status == OccurrenceStatus.SCHEDULED:
            complete_occurrence(occurrence=occurrence)
    update_activity_common(activity=event.activity, status=ActivityStatus.COMPLETED)
    return 1


def _post_event_followup(event, policy, now):
    if not policy.post_event_followup_enabled:
        return 0
    created = 0
    for occurrence in event.activity.occurrences.all():
        ended = occurrence.status == OccurrenceStatus.COMPLETED or (occurrence.end_at is not None and now >= occurrence.end_at)
        if not ended:
            continue
        for participant in _event_participants(event, occurrence=occurrence, include_cancelled=False):
            dedup = f"autopilot:followup:{occurrence.pk}:{participant.pk}"
            _, run_created = _record_once(
                event=event,
                rule_key="post-event-followup",
                dedup_key=dedup,
                summary=f"Suivi post-séance pour {participant.email}",
                payload={"occurrence_id": str(occurrence.pk)},
            )
            if not run_created:
                continue
            create_notification(
                recipient=participant,
                kind=NotificationKind.SYSTEM,
                category=NotificationCategory.EVENT,
                title=f"Merci d'avoir participé à {event.title}",
                message=(
                    "Merci d'avoir utilisé Makolo. Votre participation est enregistrée. "
                    "Les avis et recommandations personnalisées pourront s'appuyer "
                    "sur cet historique sans exposer vos données à l'organisateur."
                ),
                action_url=f"/events/{event.slug}/?occurrence={occurrence.pk}",
                dedup_key=f"notification:{dedup}",
                metadata={"event_id": str(event.pk), "occurrence_id": str(occurrence.pk)},
            )
            created += 1
    return created


def expire_due_orders(*, now=None, limit=200):
    now = now or timezone.now()
    orders = list(
        TicketOrder.objects.filter(
            status=TicketOrderStatus.PENDING,
            expires_at__isnull=False,
            expires_at__lte=now,
        ).order_by("expires_at")[:limit]
    )
    count = 0
    for order in orders:
        expire_order(order=order)
        count += 1
    return count


def recover_stale_notification_deliveries(*, now=None, stale_minutes=15):
    now = now or timezone.now()
    cutoff = now - timedelta(minutes=stale_minutes)
    return NotificationDelivery.objects.filter(
        status=DeliveryStatus.PROCESSING,
        updated_at__lt=cutoff,
    ).update(
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

    completed_cutoff = now - timedelta(days=COMPLETED_EVENT_CATCHUP_DAYS)
    completed_cutoff_date = completed_cutoff.date()
    recent_completed = Q(status=EventStatus.COMPLETED) & (
        Q(activity__occurrences__end_at__gte=completed_cutoff)
        | Q(
            activity__occurrences__end_at__isnull=True,
            activity__occurrences__end_date__gte=completed_cutoff_date,
        )
        | Q(
            activity__occurrences__end_at__isnull=True,
            activity__occurrences__end_date__isnull=True,
            activity__occurrences__start_date__gte=completed_cutoff_date,
        )
    )
    events = (
        Event.objects.filter(Q(status=EventStatus.PUBLISHED) | recent_completed)
        .select_related("activity", "activity__created_by", "activity__space", "automation_policy")
        .distinct()
        .order_by("created_at")
    )
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
        if event.status == EventStatus.COMPLETED or any(
            occurrence.end_at and occurrence.end_at <= now for occurrence in event.activity.occurrences.all()
        ):
            stats["followups"] += _post_event_followup(event, policy, now)

    stats["crm_campaigns"] = process_due_campaigns(now=now, recipient_limit=delivery_limit)
    stats["deliveries"] = dispatch_pending(limit=delivery_limit)
    return stats
