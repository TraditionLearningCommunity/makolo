from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Mapping

from asgiref.sync import sync_to_async
from django.db import connection, transaction

from prospector.budget import BudgetReservationDecision
from prospector.errors import ProspectorContractError

from .django_app.models import (
    ProspectorBudgetCounter,
    ProspectorBudgetReservation,
)


def _lock_id(value: str) -> int:
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


def _advisory_lock(value: str) -> None:
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [_lock_id(value)])


def _aware(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ProspectorContractError(f"{name} must be timezone-aware")
    return value


class DjangoBudgetStore:
    """Atomic, idempotent PostgreSQL budget reservations."""

    def reserve_sync(
        self,
        *,
        handoff_key: str,
        policy_key: str,
        scopes: Mapping[str, str],
        limits: Mapping[str, int],
        period_start: datetime,
        period_end: datetime,
        now: datetime,
    ) -> BudgetReservationDecision:
        handoff_key = str(handoff_key).strip()
        policy_key = str(policy_key).strip()
        if not handoff_key or not policy_key:
            raise ProspectorContractError("handoff_key and policy_key are required")
        period_start = _aware("period_start", period_start)
        period_end = _aware("period_end", period_end)
        now = _aware("now", now)
        if period_end <= period_start:
            raise ProspectorContractError("period_end must be after period_start")
        if not period_start <= now < period_end:
            raise ProspectorContractError("now must be inside the budget period")

        scope_map = {str(k): str(v).strip() for k, v in dict(scopes).items()}
        limit_map = dict(limits)
        if set(scope_map) != set(limit_map):
            raise ProspectorContractError("budget scopes must match budget limits exactly")
        for kind, key in scope_map.items():
            if not key:
                raise ProspectorContractError(f"budget scope {kind} must not be empty")
            value = limit_map[kind]
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ProspectorContractError(f"budget limit {kind} must be positive")

        with transaction.atomic():
            _advisory_lock(
                f"reservation:{policy_key}:{handoff_key}:{period_start.isoformat()}"
            )
            existing = ProspectorBudgetReservation.objects.filter(
                handoff_key=handoff_key,
                policy_key=policy_key,
                period_start=period_start,
            ).first()
            if existing is not None:
                if dict(existing.scopes) != scope_map or dict(existing.limits) != limit_map:
                    raise ProspectorContractError(
                        "existing handoff reservation does not match current policy scopes/limits"
                    )
                return BudgetReservationDecision(
                    allowed=True,
                    retry_at=None,
                    scopes=existing.scopes,
                    reused=True,
                )

            identifiers = sorted(
                f"{policy_key}:{kind}:{key}:{period_start.isoformat()}"
                for kind, key in scope_map.items()
            )
            for identifier in identifiers:
                _advisory_lock("counter:" + identifier)

            counters = {}
            for kind, key in sorted(scope_map.items()):
                counter, _created = ProspectorBudgetCounter.objects.get_or_create(
                    policy_key=policy_key,
                    scope_kind=kind,
                    scope_key=key,
                    period_start=period_start,
                    defaults={
                        "period_end": period_end,
                        "used_count": 0,
                    },
                )
                counter = ProspectorBudgetCounter.objects.select_for_update().get(
                    pk=counter.pk
                )
                if counter.period_end != period_end:
                    raise ProspectorContractError(
                        "existing budget counter period_end does not match current policy"
                    )
                counters[kind] = counter

            for kind, counter in counters.items():
                if counter.used_count >= limit_map[kind]:
                    return BudgetReservationDecision(
                        allowed=False,
                        retry_at=period_end,
                        scopes=scope_map,
                    )

            for counter in counters.values():
                counter.used_count += 1
                counter.period_end = period_end
                counter.save(
                    update_fields=["used_count", "period_end", "updated_at"]
                )

            ProspectorBudgetReservation.objects.create(
                handoff_key=handoff_key,
                policy_key=policy_key,
                period_start=period_start,
                period_end=period_end,
                scopes=scope_map,
                limits=limit_map,
                reserved_at=now,
            )
            return BudgetReservationDecision(
                allowed=True,
                retry_at=None,
                scopes=scope_map,
            )

    async def reserve(self, **kwargs) -> BudgetReservationDecision:
        return await sync_to_async(self.reserve_sync, thread_sensitive=True)(**kwargs)
