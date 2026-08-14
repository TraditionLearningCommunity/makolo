from __future__ import annotations

import json
import logging
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.utils import timezone

from core.logging_filters import redact_sensitive_text

from .contracts import DomainEventType
from .models import (
    DomainEventConsumption,
    DomainEventConsumptionStatus,
    DomainEventOutbox,
    DomainEventStatus,
)
from .registry import registered_consumers_for


logger = logging.getLogger(__name__)
SENSITIVE_KEY_PARTS = {
    "password",
    "secret",
    "token",
    "credential",
    "qr_code",
    "bearer",
    "kyc",
}


def _validate_json_value(value, *, path="payload"):
    if value is None or isinstance(value, (str, int, float, bool)):
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, path=f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValidationError(f"{path}: les clés JSON doivent être des chaînes.")
            normalized = key.lower().replace("-", "_")
            if any(part in normalized for part in SENSITIVE_KEY_PARTS):
                raise ValidationError(f"{path}.{key}: donnée sensible interdite dans un Domain Event.")
            _validate_json_value(item, path=f"{path}.{key}")
        return
    raise ValidationError(f"{path}: type non sérialisable dans un Domain Event.")


def validate_domain_event_payload(payload):
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise ValidationError("Le payload d’un Domain Event doit être un objet JSON.")
    _validate_json_value(payload)
    try:
        json.dumps(payload)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Le payload du Domain Event n’est pas sérialisable.") from exc
    return payload


@transaction.atomic
def emit_domain_event(
    *,
    event_type: str,
    source_type: str,
    source_id="",
    idempotency_key: str,
    payload=None,
    payload_version: int = 1,
    occurred_at=None,
    space_id=None,
    activity_id=None,
    process_on_commit: bool = True,
) -> DomainEventOutbox:
    event_type = (event_type or "").strip()
    if event_type not in DomainEventType.values:
        raise ValidationError(f"Type de Domain Event inconnu: {event_type!r}.")
    source_type = (source_type or "").strip()
    if not source_type:
        raise ValidationError("source_type est obligatoire pour un Domain Event.")
    idempotency_key = (idempotency_key or "").strip()
    if not idempotency_key:
        raise ValidationError("Une clé d’idempotence est obligatoire pour un Domain Event.")
    if len(idempotency_key) > 255:
        raise ValidationError("La clé d’idempotence du Domain Event est trop longue.")
    try:
        payload_version = int(payload_version)
    except (TypeError, ValueError) as exc:
        raise ValidationError("payload_version doit être un entier positif.") from exc
    if payload_version <= 0:
        raise ValidationError("payload_version doit être positif.")
    payload = validate_domain_event_payload(payload)
    occurred_at = occurred_at or timezone.now()

    defaults = {
        "event_type": event_type,
        "source_type": source_type[:80],
        "source_id": str(source_id or "")[:128],
        "space_id": space_id,
        "activity_id": activity_id,
        "payload_version": payload_version,
        "payload": payload,
        "occurred_at": occurred_at,
    }
    event, created = DomainEventOutbox.objects.get_or_create(
        idempotency_key=idempotency_key,
        defaults=defaults,
    )
    if not created:
        comparable = {
            "event_type": event.event_type,
            "source_type": event.source_type,
            "source_id": event.source_id,
            "space_id": event.space_id,
            "activity_id": event.activity_id,
            "payload_version": event.payload_version,
            "payload": event.payload,
        }
        expected = {key: defaults[key] for key in comparable}
        if comparable != expected:
            raise ValidationError("Cette clé d’idempotence existe avec un Domain Event différent.")
        return event

    if process_on_commit:
        transaction.on_commit(
            lambda event_id=event.pk: process_domain_events(event_ids=[event_id], batch_size=1, limit=1)
        )
    return event


def recover_stale_domain_events(*, now=None, stale_minutes: int = 15) -> int:
    now = now or timezone.now()
    cutoff = now - timedelta(minutes=stale_minutes)
    stale = DomainEventOutbox.objects.filter(
        status=DomainEventStatus.PROCESSING,
        claimed_at__lt=cutoff,
    )
    recovered = stale.filter(attempts__lt=models_f("max_attempts")).update(
        status=DomainEventStatus.PENDING,
        claimed_at=None,
        last_error="Reprise après interruption du processor.",
        updated_at=now,
    )
    stale.filter(attempts__gte=models_f("max_attempts")).update(
        status=DomainEventStatus.FAILED,
        claimed_at=None,
        last_error="Nombre maximal de tentatives atteint après interruption.",
        updated_at=now,
    )
    return recovered


def models_f(field):
    # Local helper keeps django.db.models out of the hot import path above.
    from django.db.models import F

    return F(field)


def _claim_event_ids(*, batch_size: int, event_ids=None):
    now = timezone.now()
    with transaction.atomic():
        queryset = DomainEventOutbox.objects.filter(status=DomainEventStatus.PENDING)
        if event_ids is not None:
            queryset = queryset.filter(pk__in=event_ids)
        queryset = queryset.order_by("created_at", "id")
        if connection.features.has_select_for_update:
            lock_kwargs = {"of": ("self",)}
            if connection.features.has_select_for_update_skip_locked:
                lock_kwargs["skip_locked"] = True
            queryset = queryset.select_for_update(**lock_kwargs)
        events = list(queryset[: max(int(batch_size), 1)])
        for event in events:
            event.status = DomainEventStatus.PROCESSING
            event.attempts += 1
            event.claimed_at = now
            event.last_error = ""
            event.updated_at = now
        if events:
            DomainEventOutbox.objects.bulk_update(
                events,
                ["status", "attempts", "claimed_at", "last_error", "updated_at"],
            )
        return [event.pk for event in events]


def _begin_consumption(event, consumer_name):
    with transaction.atomic():
        consumption, _ = DomainEventConsumption.objects.get_or_create(
            event=event,
            consumer=consumer_name,
        )
        consumption = (
            DomainEventConsumption.objects.select_for_update(of=("self",))
            .order_by()
            .get(pk=consumption.pk)
        )
        if consumption.status in {
            DomainEventConsumptionStatus.PROCESSED,
            DomainEventConsumptionStatus.SKIPPED,
        }:
            return None
        if consumption.attempts >= consumption.max_attempts:
            consumption.status = DomainEventConsumptionStatus.FAILED
            consumption.save(update_fields=["status", "updated_at"])
            return None
        consumption.status = DomainEventConsumptionStatus.PROCESSING
        consumption.attempts += 1
        consumption.last_error = ""
        consumption.save(update_fields=["status", "attempts", "last_error", "updated_at"])
        return consumption.pk


def _finish_consumption(consumption_id, *, success, error=""):
    now = timezone.now()
    with transaction.atomic():
        consumption = (
            DomainEventConsumption.objects.select_for_update(of=("self",))
            .order_by()
            .get(pk=consumption_id)
        )
        if success:
            consumption.status = DomainEventConsumptionStatus.PROCESSED
            consumption.processed_at = now
            consumption.last_error = ""
        else:
            consumption.status = DomainEventConsumptionStatus.FAILED
            consumption.last_error = redact_sensitive_text(error)[:1000]
        consumption.save(
            update_fields=["status", "processed_at", "last_error", "updated_at"]
        )
        return consumption


def _process_claimed_event(event_id):
    event = DomainEventOutbox.objects.get(pk=event_id)
    failures = []
    for consumer in registered_consumers_for(event.event_type):
        consumption_id = _begin_consumption(event, consumer.name)
        if consumption_id is None:
            existing = DomainEventConsumption.objects.filter(
                event=event,
                consumer=consumer.name,
                status=DomainEventConsumptionStatus.FAILED,
            ).first()
            if existing and existing.attempts >= existing.max_attempts:
                failures.append(f"{consumer.name}: max attempts")
            continue
        try:
            consumer.handler(event)
        except Exception as exc:  # Consumers are isolated; the outbox remains recoverable.
            safe_error = redact_sensitive_text(str(exc))[:1000]
            _finish_consumption(consumption_id, success=False, error=safe_error)
            failures.append(f"{consumer.name}: {safe_error[:180]}")
            logger.exception(
                "DomainEvent consumer failed event_id=%s event_type=%s consumer=%s",
                event.pk,
                event.event_type,
                consumer.name,
            )
        else:
            _finish_consumption(consumption_id, success=True)

    now = timezone.now()
    event.refresh_from_db(fields=["attempts", "max_attempts"])
    if failures:
        terminal = event.attempts >= event.max_attempts
        DomainEventOutbox.objects.filter(pk=event.pk).update(
            status=DomainEventStatus.FAILED if terminal else DomainEventStatus.PENDING,
            claimed_at=None,
            processed_at=None,
            last_error="; ".join(failures)[:1000],
            updated_at=now,
        )
        return "failed" if terminal else "retry"

    DomainEventOutbox.objects.filter(pk=event.pk).update(
        status=DomainEventStatus.PROCESSED,
        claimed_at=None,
        processed_at=now,
        last_error="",
        updated_at=now,
    )
    return "processed"


def process_domain_events(*, batch_size: int = 100, limit: int | None = None, event_ids=None):
    batch_size = max(int(batch_size), 1)
    remaining = None if limit is None else max(int(limit), 0)
    stats = {"claimed": 0, "processed": 0, "retry": 0, "failed": 0}
    if remaining == 0:
        return stats

    ids_filter = list(event_ids) if event_ids is not None else None
    while True:
        size = batch_size if remaining is None else min(batch_size, remaining)
        if size <= 0:
            break
        claimed = _claim_event_ids(batch_size=size, event_ids=ids_filter)
        if not claimed:
            break
        stats["claimed"] += len(claimed)
        for event_id in claimed:
            outcome = _process_claimed_event(event_id)
            stats[outcome] = stats.get(outcome, 0) + 1
        if remaining is not None:
            remaining -= len(claimed)
        if ids_filter is not None:
            claimed_set = set(claimed)
            ids_filter = [event_id for event_id in ids_filter if event_id not in claimed_set]
            if not ids_filter:
                break
    return stats
