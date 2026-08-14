from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from activities.models import Activity
from commerce.models import CommerceOrder
from core.logging_filters import redact_sensitive_text
from domain_events.registry import register_consumer
from journeys.models import Journey
from access.models import Access
from notifications.models import NotificationCategory, NotificationKind
from notifications.services import create_notification

from .models import (
    AutomationExecution,
    AutomationRule,
    DomainAutomationActionKind,
    DomainAutomationExecutionStatus,
)


User = get_user_model()
CONSUMER_NAME = "automation.rules"


def _conditions_match(rule, event):
    payload = event.payload or {}
    for key in ("workflow", "payment_mode", "status", "currency"):
        if key in rule.conditions and payload.get(key) != rule.conditions[key]:
            return False
    if "amount_gte" in rule.conditions:
        try:
            amount = Decimal(str(payload.get("amount")))
            threshold = Decimal(str(rule.conditions["amount_gte"]))
        except (InvalidOperation, TypeError, ValueError):
            return False
        if amount < threshold:
            return False
    return True


def _recipient_for(rule, event):
    selector = rule.action_config.get("recipient", "beneficiary")
    field = {
        "beneficiary": "beneficiary_id",
        "initiated_by": "initiated_by_id",
        "buyer": "buyer_id",
        "requester": "requester_id",
    }[selector]
    recipient_id = (event.payload or {}).get(field)
    if not recipient_id:
        raise ValueError(f"Le Domain Event ne fournit pas {field} pour cette règle.")
    recipient = User.objects.filter(pk=recipient_id, is_active=True).first()
    if recipient is None:
        raise ValueError("Le destinataire Automation n’existe plus ou est inactif.")
    return recipient


def _canonical_context(event):
    payload = event.payload or {}
    activity = Activity.objects.filter(pk=event.activity_id).first() if event.activity_id else None
    journey = Journey.objects.filter(pk=payload.get("journey_id")).first() if payload.get("journey_id") else None
    access = Access.objects.filter(pk=payload.get("access_id")).first() if payload.get("access_id") else None
    commerce_order = (
        CommerceOrder.objects.filter(pk=payload.get("commerce_order_id")).first()
        if payload.get("commerce_order_id")
        else None
    )
    return activity, journey, access, commerce_order


def _start_execution(rule, event):
    with transaction.atomic():
        execution, _ = AutomationExecution.objects.get_or_create(
            rule=rule,
            domain_event=event,
            defaults={"action": rule.action_kind},
        )
        execution = (
            AutomationExecution.objects.select_for_update(of=("self",))
            .order_by()
            .get(pk=execution.pk)
        )
        if execution.status in {
            DomainAutomationExecutionStatus.COMPLETED,
            DomainAutomationExecutionStatus.SKIPPED,
        }:
            return None, execution.status
        if execution.attempts >= execution.max_attempts:
            return None, "exhausted"
        if not _conditions_match(rule, event):
            execution.status = DomainAutomationExecutionStatus.SKIPPED
            execution.completed_at = timezone.now()
            execution.last_error = ""
            execution.save(update_fields=["status", "completed_at", "last_error", "updated_at"])
            return None, DomainAutomationExecutionStatus.SKIPPED
        execution.status = DomainAutomationExecutionStatus.RUNNING
        execution.attempts += 1
        execution.started_at = timezone.now()
        execution.last_error = ""
        execution.save(update_fields=["status", "attempts", "started_at", "last_error", "updated_at"])
        return execution.pk, DomainAutomationExecutionStatus.RUNNING


def _finish_execution(execution_id, *, success, error=""):
    with transaction.atomic():
        execution = (
            AutomationExecution.objects.select_for_update(of=("self",))
            .order_by()
            .get(pk=execution_id)
        )
        if success:
            execution.status = DomainAutomationExecutionStatus.COMPLETED
            execution.completed_at = timezone.now()
            execution.last_error = ""
        else:
            execution.status = DomainAutomationExecutionStatus.FAILED
            execution.last_error = redact_sensitive_text(error)[:1000]
        execution.save(update_fields=["status", "completed_at", "last_error", "updated_at"])
        return execution


def _execute_notification(rule, event):
    recipient = _recipient_for(rule, event)
    activity, journey, access, commerce_order = _canonical_context(event)
    config = rule.action_config
    return create_notification(
        recipient=recipient,
        kind=NotificationKind.SYSTEM,
        category=config.get("category", NotificationCategory.SYSTEM),
        title=str(config["title"]),
        message=str(config["message"]),
        dedup_key=f"automation:{rule.pk}:{event.pk}:{recipient.pk}",
        metadata={"automation_rule_id": str(rule.pk), "domain_event_id": str(event.pk)},
        queue_email=config.get("queue_email", True),
        domain_event=event,
        activity=activity,
        journey=journey,
        access=access,
        commerce_order=commerce_order,
        template_key="automation.rule",
    )


def _run_rule(rule, event):
    execution_id, state = _start_execution(rule, event)
    if execution_id is None:
        return state
    try:
        if rule.action_kind == DomainAutomationActionKind.NOTIFICATION:
            _execute_notification(rule, event)
        else:
            raise ValueError("Action Automation non supportée.")
    except Exception as exc:
        _finish_execution(execution_id, success=False, error=str(exc))
        raise
    _finish_execution(execution_id, success=True)
    return DomainAutomationExecutionStatus.COMPLETED


def consume_automation_event(event):
    if not event.space_id:
        return
    scope = Q(activity__isnull=True)
    if event.activity_id:
        scope |= Q(activity_id=event.activity_id)
    rules = list(
        AutomationRule.objects.filter(
            space_id=event.space_id,
            trigger_event_type=event.event_type,
            is_active=True,
        )
        .filter(scope)
        .order_by("id")
    )
    failures = []
    for rule in rules:
        try:
            _run_rule(rule, event)
        except Exception as exc:
            failures.append((rule.pk, redact_sensitive_text(str(exc))[:180]))
    if failures:
        raise RuntimeError(f"{len(failures)} règle(s) Automation ont échoué pour ce Domain Event.")


register_consumer(CONSUMER_NAME, consume_automation_event)
