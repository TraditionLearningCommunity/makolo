from datetime import datetime, timedelta

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from accounts.models import NotificationPreference
from core.logging_filters import redact_sensitive_text

from .models import (
    DeliveryChannel,
    DeliveryStatus,
    Notification,
    NotificationCategory,
    NotificationDelivery,
    NotificationKind,
)
from .selectors import get_due_deliveries


def _preferences_for(user):
    return NotificationPreference.objects.filter(user=user).first()


def _category_allowed(preferences, category: str) -> bool:
    if not preferences:
        return True
    if not preferences.email_notifications:
        return False
    if category in {NotificationCategory.EVENT, NotificationCategory.TICKET}:
        return preferences.event_notifications
    if category == NotificationCategory.SECURITY:
        return preferences.security_notifications
    if category == NotificationCategory.MARKETING:
        return preferences.marketing_notifications
    if category == NotificationCategory.SERVICE:
        return preferences.service_notifications
    if category == NotificationCategory.OPPORTUNITY:
        return preferences.opportunity_notifications
    return True


def _quiet_hours_release(preferences, now=None):
    now = now or timezone.now()
    if (
        not preferences
        or not preferences.quiet_hours_enabled
        or not preferences.quiet_hours_start
        or not preferences.quiet_hours_end
    ):
        return now

    local_now = timezone.localtime(now)
    current = local_now.time().replace(tzinfo=None)
    start = preferences.quiet_hours_start
    end = preferences.quiet_hours_end

    if start == end:
        return now

    if start < end:
        in_quiet = start <= current < end
        target_date = local_now.date()
    else:
        in_quiet = current >= start or current < end
        target_date = local_now.date() + (timedelta(days=1) if current >= start else timedelta())

    if not in_quiet:
        return now

    naive_target = datetime.combine(target_date, end)
    return timezone.make_aware(naive_target, timezone.get_current_timezone())


def _public_url(path: str) -> str:
    if not path:
        return ""
    if path.startswith("http://") or path.startswith("https://"):
        return path
    configured = getattr(settings, "MAKOLO_PUBLIC_BASE_URL", "").rstrip("/")
    if not configured:
        raise ImproperlyConfigured("MAKOLO_PUBLIC_BASE_URL doit être configurée.")
    return f"{configured}/{path.lstrip('/')}"


@transaction.atomic
def create_notification(
    *,
    recipient,
    kind: str,
    category: str,
    title: str,
    message: str,
    action_url: str = "",
    dedup_key: str | None = None,
    metadata: dict | None = None,
    queue_email: bool = True,
    domain_event=None,
    activity=None,
    journey=None,
    access=None,
    commerce_order=None,
    template_key: str = "",
) -> Notification:
    defaults = {
        "recipient": recipient,
        "domain_event": domain_event,
        "activity": activity,
        "journey": journey,
        "access": access,
        "commerce_order": commerce_order,
        "template_key": (template_key or "")[:100],
        "kind": kind,
        "category": category,
        "title": title[:180],
        "message": message,
        "action_url": action_url[:500],
        "metadata": metadata or {},
    }
    if dedup_key:
        notification, created = Notification.objects.get_or_create(
            dedup_key=dedup_key[:255],
            defaults=defaults,
        )
        if not created:
            return notification
    else:
        notification = Notification.objects.create(**defaults)

    if queue_email:
        email = (getattr(recipient, "email", "") or "").strip().lower()
        preferences = _preferences_for(recipient)
        allowed = bool(email) and _category_allowed(preferences, category)
        scheduled_for = _quiet_hours_release(preferences)
        status = DeliveryStatus.QUEUED if allowed else DeliveryStatus.SKIPPED
        reason = ""
        if not email:
            reason = "Le destinataire ne possède pas d’adresse e-mail."
        elif not allowed:
            reason = "Les préférences utilisateur désactivent cet envoi e-mail."

        NotificationDelivery.objects.create(
            notification=notification,
            channel=DeliveryChannel.EMAIL,
            destination=email or f"user:{recipient.pk}",
            status=status,
            scheduled_for=scheduled_for,
            skipped_reason=reason,
        )

    return notification


def _claim_delivery(delivery_id):
    with transaction.atomic():
        delivery = (
            NotificationDelivery.objects.select_for_update()
            .select_related("notification", "notification__recipient")
            .get(pk=delivery_id)
        )
        if delivery.status != DeliveryStatus.QUEUED:
            return None
        if delivery.scheduled_for > timezone.now():
            return None
        delivery.status = DeliveryStatus.PROCESSING
        delivery.attempts += 1
        delivery.last_error = ""
        delivery.save(update_fields=["status", "attempts", "last_error", "updated_at"])
        return delivery


def dispatch_delivery(delivery_id) -> str:
    delivery = _claim_delivery(delivery_id)
    if not delivery:
        return "ignored"

    if delivery.channel != DeliveryChannel.EMAIL:
        NotificationDelivery.objects.filter(pk=delivery.pk).update(
            status=DeliveryStatus.SKIPPED,
            skipped_reason="Canal non implémenté dans ce socle.",
            updated_at=timezone.now(),
        )
        return "skipped"

    notification = delivery.notification
    action_url = _public_url(notification.action_url)
    context = {
        "notification": notification,
        "recipient": notification.recipient,
        "action_url": action_url,
    }
    text_body = render_to_string("notifications/email/notification.txt", context)
    html_body = render_to_string("notifications/email/notification.html", context)

    try:
        email = EmailMultiAlternatives(
            subject=f"Makolo — {notification.title}",
            body=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[delivery.destination],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=False)
    except Exception as exc:
        now = timezone.now()
        delivery.refresh_from_db(fields=["attempts", "max_attempts"])
        terminal = delivery.attempts >= delivery.max_attempts
        NotificationDelivery.objects.filter(pk=delivery.pk).update(
            status=DeliveryStatus.FAILED if terminal else DeliveryStatus.QUEUED,
            last_error=redact_sensitive_text(str(exc))[:1000],
            scheduled_for=now + timedelta(minutes=max(delivery.attempts, 1) * 5),
            updated_at=now,
        )
        return "failed" if terminal else "retry"

    now = timezone.now()
    NotificationDelivery.objects.filter(pk=delivery.pk).update(
        status=DeliveryStatus.SENT,
        sent_at=now,
        last_error="",
        updated_at=now,
    )
    return "sent"


def dispatch_pending(*, limit: int = 100) -> dict[str, int]:
    result = {"sent": 0, "retry": 0, "failed": 0, "skipped": 0, "ignored": 0}
    delivery_ids = list(get_due_deliveries(limit=limit).values_list("pk", flat=True))
    for delivery_id in delivery_ids:
        outcome = dispatch_delivery(delivery_id)
        result[outcome] = result.get(outcome, 0) + 1
    return result


def schedule_event_reminders(*, hours_before: int = 24, window_minutes: int = 60) -> int:
    from tickets.models import Ticket, TicketStatus

    now = timezone.now()
    target = now + timedelta(hours=hours_before)
    start = target - timedelta(minutes=window_minutes // 2)
    end = target + timedelta(minutes=window_minutes // 2)

    tickets = (
        Ticket.objects.filter(
            status=TicketStatus.VALID,
            owner__isnull=False,
            event__start_at__gte=start,
            event__start_at__lt=end,
        )
        .select_related("owner", "event", "event__venue")
        .order_by("event_id", "owner_id")
    )

    pairs = {}
    for ticket in tickets:
        pairs[(ticket.event_id, ticket.owner_id)] = ticket

    created = 0
    for ticket in pairs.values():
        event = ticket.event
        venue = str(event.venue) if event.venue_id else "lieu à confirmer"
        dedup_key = f"event-reminder:{hours_before}h:{event.pk}:{ticket.owner_id}"
        before = Notification.objects.filter(dedup_key=dedup_key).exists()
        create_notification(
            recipient=ticket.owner,
            kind=NotificationKind.EVENT_REMINDER,
            category=NotificationCategory.EVENT,
            title=f"Rappel — {event.title}",
            message=(
                f"Votre événement « {event.title} » commence le "
                f"{timezone.localtime(event.start_at).strftime('%d/%m/%Y à %H:%M')} — {venue}. "
                "Pensez à préparer votre billet et son QR code."
            ),
            action_url=reverse("events:detail", kwargs={"slug": event.slug}),
            dedup_key=dedup_key,
            metadata={"event_id": str(event.pk), "hours_before": hours_before},
        )
        if not before:
            created += 1
    return created


def notify_waitlist_offer(entry_id):
    from tickets.notifications import notify_waitlist_offer as implementation

    return implementation(entry_id)


def notify_ticket_transfer_created(transfer_id):
    from tickets.notifications import notify_ticket_transfer_created as implementation

    return implementation(transfer_id)


def notify_ticket_transfer_accepted(transfer_id):
    from tickets.notifications import notify_ticket_transfer_accepted as implementation

    return implementation(transfer_id)
