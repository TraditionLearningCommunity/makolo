from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .django_app.models import ObserverScopeState
from .errors import ObserverStateConflictError
from .http_contracts import HostLease, RobotsCache, ScopeDeferred


def _aware(name: str, value: datetime | None) -> datetime:
    value = value or timezone.now()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")
    return value


def _scope_key(hostname: str) -> str:
    value = (hostname or "").strip().rstrip(".").lower()
    if not value:
        raise ValueError("hostname must not be empty")
    return value


def _get_or_create_locked(hostname: str) -> ObserverScopeState:
    key = _scope_key(hostname)
    row = (
        ObserverScopeState.objects.select_for_update()
        .filter(scope_kind="host", scope_key=key)
        .first()
    )
    if row is not None:
        return row
    try:
        with transaction.atomic():
            ObserverScopeState.objects.create(
                scope_kind="host",
                scope_key=key,
            )
    except IntegrityError:
        pass
    return ObserverScopeState.objects.select_for_update().get(
        scope_kind="host",
        scope_key=key,
    )


@transaction.atomic
def reserve_host_request(
    hostname: str,
    *,
    now: datetime | None = None,
    min_interval_seconds: float,
    lease_seconds: int,
) -> HostLease:
    now = _aware("now", now)
    state = _get_or_create_locked(hostname)

    if (
        state.lease_token is not None
        and state.lease_expires_at is not None
        and state.lease_expires_at > now
    ):
        raise ScopeDeferred(state.lease_expires_at)
    if state.not_before is not None and state.not_before > now:
        raise ScopeDeferred(state.not_before)

    token = uuid.uuid4()
    state.lease_token = token
    state.lease_expires_at = now + timedelta(seconds=lease_seconds)
    state.last_request_at = now
    interval_due = now + timedelta(seconds=min_interval_seconds)
    if state.not_before is None or interval_due > state.not_before:
        state.not_before = interval_due
    state.save(
        update_fields=[
            "lease_token",
            "lease_expires_at",
            "last_request_at",
            "not_before",
            "updated_at",
        ]
    )
    return HostLease(
        scope_key=state.scope_key,
        token=str(token),
        lease_expires_at=state.lease_expires_at,
    )


@transaction.atomic
def renew_host_lease(
    lease: HostLease,
    *,
    lease_seconds: int,
    now: datetime | None = None,
) -> HostLease:
    now = _aware("now", now)
    state = ObserverScopeState.objects.select_for_update().get(
        scope_kind="host",
        scope_key=lease.scope_key,
    )
    if str(state.lease_token) != lease.token:
        raise ObserverStateConflictError(
            "HTTP host lease is no longer current"
        )
    state.lease_expires_at = now + timedelta(seconds=lease_seconds)
    state.save(update_fields=["lease_expires_at", "updated_at"])
    return HostLease(
        scope_key=state.scope_key,
        token=lease.token,
        lease_expires_at=state.lease_expires_at,
    )


@transaction.atomic
def release_host_lease(lease: HostLease) -> bool:
    state = (
        ObserverScopeState.objects.select_for_update()
        .filter(scope_kind="host", scope_key=lease.scope_key)
        .first()
    )
    if state is None or str(state.lease_token) != lease.token:
        return False
    state.lease_token = None
    state.lease_expires_at = None
    state.save(
        update_fields=[
            "lease_token",
            "lease_expires_at",
            "updated_at",
        ]
    )
    return True


@transaction.atomic
def defer_host_until(
    hostname: str,
    *,
    not_before: datetime,
) -> datetime:
    not_before = _aware("not_before", not_before)
    state = _get_or_create_locked(hostname)
    if state.not_before is None or not_before > state.not_before:
        state.not_before = not_before
        state.save(update_fields=["not_before", "updated_at"])
    return state.not_before


def get_cached_robots(
    hostname: str,
    *,
    now: datetime | None = None,
) -> RobotsCache | None:
    now = _aware("now", now)
    state = ObserverScopeState.objects.filter(
        scope_kind="host",
        scope_key=_scope_key(hostname),
    ).first()
    if (
        state is None
        or state.robots_status is None
        or state.robots_checked_at is None
        or state.robots_expires_at is None
        or state.robots_expires_at <= now
    ):
        return None
    return RobotsCache(
        status=state.robots_status,
        body=state.robots_body,
        checked_at=state.robots_checked_at,
        expires_at=state.robots_expires_at,
    )


@transaction.atomic
def cache_robots(
    hostname: str,
    *,
    status: int,
    body: str,
    checked_at: datetime,
    expires_at: datetime,
) -> RobotsCache:
    checked_at = _aware("checked_at", checked_at)
    expires_at = _aware("expires_at", expires_at)
    cache = RobotsCache(
        status=status,
        body=body,
        checked_at=checked_at,
        expires_at=expires_at,
    )
    state = _get_or_create_locked(hostname)
    state.robots_status = cache.status
    state.robots_body = cache.body
    state.robots_checked_at = cache.checked_at
    state.robots_expires_at = cache.expires_at
    state.save(
        update_fields=[
            "robots_status",
            "robots_body",
            "robots_checked_at",
            "robots_expires_at",
            "updated_at",
        ]
    )
    return cache
