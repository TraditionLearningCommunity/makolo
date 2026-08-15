from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import transaction

from activities.models import Activity, Occurrence
from domain_events.contracts import DomainEventType
from domain_events.registry import register_consumer
from organizations.models import Organization

from .models import AnalyticsFact


CONSUMER_NAME = "analytics.system"
ANALYTICS_EVENT_TYPES = {
    DomainEventType.JOURNEY_SUBMITTED,
    DomainEventType.JOURNEY_APPROVED,
    DomainEventType.JOURNEY_REJECTED,
    DomainEventType.JOURNEY_CONFIRMED,
    DomainEventType.JOURNEY_FULFILLED,
    DomainEventType.JOURNEY_CANCELLED,
    DomainEventType.REQUEST_APPROVED,
    DomainEventType.REQUEST_REJECTED,
    DomainEventType.COMMERCE_ORDER_CONFIRMED,
    DomainEventType.COMMERCE_ORDER_CANCELLED,
    DomainEventType.PAYMENT_SUCCEEDED,
    DomainEventType.PAYMENT_REFUNDED,
    DomainEventType.ACCESS_ISSUED,
    DomainEventType.ACCESS_USED,
    DomainEventType.ACCESS_REVOKED,
    DomainEventType.OCCURRENCE_CANCELLED,
    DomainEventType.OCCURRENCE_RESCHEDULED,
}


def _safe_decimal(value):
    if value in {None, ""}:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _profile_id(payload):
    return payload.get("beneficiary_id") or payload.get("buyer_id") or payload.get("requester_id")


@transaction.atomic
def consume_analytics_event(domain_event):
    if domain_event.event_type not in ANALYTICS_EVENT_TYPES:
        return

    payload = domain_event.payload or {}
    space = Organization.objects.filter(pk=domain_event.space_id).first() if domain_event.space_id else None
    activity = Activity.objects.filter(pk=domain_event.activity_id).first() if domain_event.activity_id else None
    occurrence = None
    occurrence_id = payload.get("occurrence_id")
    if occurrence_id:
        occurrence = Occurrence.objects.filter(pk=occurrence_id).first()
        if occurrence is not None and activity is not None and occurrence.activity_id != activity.pk:
            occurrence = None

    profile = None
    profile_id = _profile_id(payload)
    if profile_id:
        profile = get_user_model().objects.filter(pk=profile_id).first()

    numeric_value = None
    currency = ""
    if domain_event.event_type in {
        DomainEventType.COMMERCE_ORDER_CONFIRMED,
        DomainEventType.PAYMENT_SUCCEEDED,
    }:
        numeric_value = _safe_decimal(payload.get("amount"))
        currency = (payload.get("currency") or "").strip().upper()[:3]

    AnalyticsFact.objects.get_or_create(
        domain_event=domain_event,
        fact_type=domain_event.event_type,
        defaults={
            "space": space,
            "activity": activity,
            "occurrence": occurrence,
            "profile": profile,
            "numeric_value": numeric_value,
            "currency": currency,
            "occurred_at": domain_event.occurred_at,
        },
    )


register_consumer(CONSUMER_NAME, consume_analytics_event, event_types=ANALYTICS_EVENT_TYPES)
