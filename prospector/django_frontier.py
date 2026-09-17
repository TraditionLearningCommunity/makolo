from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta
from typing import Mapping, Optional, Sequence

from asgiref.sync import sync_to_async
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from prospector.canonicalization import canonicalize_locator
from prospector.contracts import (
    ProspectingCandidate,
    ProspectingEvidence,
    ProspectingTarget,
)
from prospector.errors import FrontierClaimError, FrontierConflictError, ProspectorContractError
from prospector.frontier import FrontierClaim, FrontierState

from .django_app.models import ProspectorFrontierEntry, ProspectorFrontierEvidence


MAX_CLAIM_BATCH = 500
MAX_LEASE_SECONDS = 24 * 60 * 60


def _required_text(name: str, value: str, *, max_length: Optional[int] = None) -> str:
    if not isinstance(value, str):
        raise ProspectorContractError(f"{name} must be a string")
    value = value.strip()
    if not value:
        raise ProspectorContractError(f"{name} must not be empty")
    if max_length is not None and len(value) > max_length:
        raise ProspectorContractError(f"{name} exceeds maximum length {max_length}")
    return value


def _aware(name: str, value: datetime) -> datetime:
    if not isinstance(value, datetime) or timezone.is_naive(value):
        raise ProspectorContractError(f"{name} must be timezone-aware")
    return value


def _json_mapping(name: str, value: Mapping) -> dict:
    if not isinstance(value, Mapping):
        raise ProspectorContractError(f"{name} must be a mapping")
    data = dict(value)
    try:
        json.dumps(data, ensure_ascii=False, allow_nan=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise ProspectorContractError(f"{name} must be JSON-serializable") from exc
    return data


def _evidence_key(
    evidence: ProspectingEvidence,
    *,
    policy_context: Mapping,
    observation_hints: Mapping,
) -> str:
    payload = {
        "method": evidence.method,
        "source_target_key": evidence.source_target_key or "",
        "source_observation_ref": evidence.source_observation_ref or "",
        "provider": evidence.provider or "",
        "attributes": _json_mapping("evidence.attributes", evidence.attributes),
        "policy_context": _json_mapping("policy_context", policy_context),
        "observation_hints": _json_mapping("observation_hints", observation_hints),
    }
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _lock_queryset(queryset, *, skip_locked: bool = False):
    if not connection.features.has_select_for_update:
        return queryset
    kwargs = {"of": ("self",)}
    if skip_locked and connection.features.has_select_for_update_skip_locked:
        kwargs["skip_locked"] = True
    return queryset.select_for_update(**kwargs)


def _entry_target(entry: ProspectorFrontierEntry) -> ProspectingTarget:
    evidence = tuple(
        ProspectingEvidence(
            method=row.method,
            discovered_at=row.last_discovered_at,
            source_target_key=row.source_target_key or None,
            source_observation_ref=row.source_observation_ref or None,
            provider=row.provider or None,
            attributes=row.attributes,
        )
        for row in entry.evidence_rows.order_by("first_discovered_at", "id")
    )
    if not evidence:
        raise FrontierConflictError(
            f"frontier target {entry.target_key!r} has no durable provenance"
        )
    return ProspectingTarget(
        target_key=entry.target_key,
        locator=entry.locator,
        kind=entry.kind,
        first_discovered_at=entry.first_discovered_at,
        evidence=evidence,
        policy_context=entry.policy_context,
        observation_hints=entry.observation_hints,
    )


class DjangoFrontierStore:
    """Django/PostgreSQL adapter implementing the framework-free Frontier port."""

    def admit_sync(
        self,
        candidate: ProspectingCandidate,
        *,
        available_at: Optional[datetime] = None,
    ) -> ProspectingTarget:
        canonical = canonicalize_locator(kind=candidate.kind, locator=candidate.locator)
        policy_context = _json_mapping("policy_context", candidate.policy_context)
        observation_hints = _json_mapping("observation_hints", candidate.observation_hints)
        first_discovered_at = min(item.discovered_at for item in candidate.evidence)
        last_discovered_at = max(item.discovered_at for item in candidate.evidence)
        initial_available_at = _aware(
            "available_at",
            available_at if available_at is not None else first_discovered_at,
        )

        with transaction.atomic():
            entry, created = ProspectorFrontierEntry.objects.get_or_create(
                target_key=canonical.target_key,
                defaults={
                    "kind": canonical.kind,
                    "locator": canonical.locator,
                    "status": FrontierState.READY.value,
                    "available_at": initial_available_at,
                    "first_discovered_at": first_discovered_at,
                    "last_discovered_at": last_discovered_at,
                    "discovery_count": 1,
                    "policy_context": policy_context,
                    "observation_hints": observation_hints,
                },
            )
            entry = _lock_queryset(
                ProspectorFrontierEntry.objects.filter(pk=entry.pk)
            ).get()

            if entry.kind != canonical.kind or entry.locator != canonical.locator:
                raise FrontierConflictError(
                    "target_key collision: stored canonical target differs from candidate"
                )

            if not created:
                entry.first_discovered_at = min(
                    entry.first_discovered_at,
                    first_discovered_at,
                )
                entry.last_discovered_at = max(
                    entry.last_discovered_at,
                    last_discovered_at,
                )
                entry.discovery_count += 1
                entry.policy_context = policy_context
                entry.observation_hints = observation_hints
                entry.save(
                    update_fields=[
                        "first_discovered_at",
                        "last_discovered_at",
                        "discovery_count",
                        "policy_context",
                        "observation_hints",
                        "updated_at",
                    ]
                )

            for evidence in candidate.evidence:
                method = _required_text("evidence.method", evidence.method, max_length=80)
                source_target_key = (evidence.source_target_key or "").strip()
                source_observation_ref = (evidence.source_observation_ref or "").strip()
                provider = (evidence.provider or "").strip()
                if len(source_target_key) > 128:
                    raise ProspectorContractError("source_target_key exceeds maximum length 128")
                if len(source_observation_ref) > 255:
                    raise ProspectorContractError(
                        "source_observation_ref exceeds maximum length 255"
                    )
                if len(provider) > 160:
                    raise ProspectorContractError("provider exceeds maximum length 160")
                attributes = _json_mapping("evidence.attributes", evidence.attributes)
                key = _evidence_key(
                    evidence,
                    policy_context=policy_context,
                    observation_hints=observation_hints,
                )
                row, evidence_created = ProspectorFrontierEvidence.objects.get_or_create(
                    frontier_entry=entry,
                    evidence_key=key,
                    defaults={
                        "method": method,
                        "source_target_key": source_target_key,
                        "source_observation_ref": source_observation_ref,
                        "provider": provider,
                        "attributes": attributes,
                        "policy_context": policy_context,
                        "observation_hints": observation_hints,
                        "first_discovered_at": evidence.discovered_at,
                        "last_discovered_at": evidence.discovered_at,
                        "discovery_count": 1,
                    },
                )
                if not evidence_created:
                    row = _lock_queryset(
                        ProspectorFrontierEvidence.objects.filter(pk=row.pk)
                    ).get()
                    row.first_discovered_at = min(
                        row.first_discovered_at,
                        evidence.discovered_at,
                    )
                    row.last_discovered_at = max(
                        row.last_discovered_at,
                        evidence.discovered_at,
                    )
                    row.discovery_count += 1
                    row.save(
                        update_fields=[
                            "first_discovered_at",
                            "last_discovered_at",
                            "discovery_count",
                            "updated_at",
                        ]
                    )

            entry.refresh_from_db()
            return _entry_target(entry)

    async def admit(self, candidate: ProspectingCandidate) -> ProspectingTarget:
        return await sync_to_async(self.admit_sync, thread_sensitive=True)(candidate)

    def claim_sync(
        self,
        *,
        worker_id: str,
        limit: int,
        lease_seconds: int = 300,
        now: Optional[datetime] = None,
    ) -> Sequence[FrontierClaim]:
        worker_id = _required_text("worker_id", worker_id, max_length=120)
        try:
            limit = int(limit)
            lease_seconds = int(lease_seconds)
        except (TypeError, ValueError) as exc:
            raise ProspectorContractError("limit and lease_seconds must be integers") from exc
        if not 1 <= limit <= MAX_CLAIM_BATCH:
            raise ProspectorContractError(
                f"limit must be between 1 and {MAX_CLAIM_BATCH}"
            )
        if not 1 <= lease_seconds <= MAX_LEASE_SECONDS:
            raise ProspectorContractError(
                f"lease_seconds must be between 1 and {MAX_LEASE_SECONDS}"
            )
        now = _aware("now", now or timezone.now())
        leased_until = now + timedelta(seconds=lease_seconds)

        with transaction.atomic():
            queryset = ProspectorFrontierEntry.objects.filter(
                Q(
                    status=FrontierState.READY.value,
                    available_at__lte=now,
                )
                | Q(
                    status=FrontierState.CLAIMED.value,
                    lease_expires_at__lte=now,
                )
            ).order_by("priority", "available_at", "id")
            queryset = _lock_queryset(queryset, skip_locked=True)
            entries = list(queryset[:limit])

            claims = []
            for entry in entries:
                token = uuid.uuid4()
                entry.status = FrontierState.CLAIMED.value
                entry.claim_token = token
                entry.claimed_by = worker_id
                entry.claimed_at = now
                entry.lease_expires_at = leased_until
                entry.completed_at = None
                claims.append(
                    FrontierClaim(
                        claim_token=str(token),
                        worker_id=worker_id,
                        leased_until=leased_until,
                        target=_entry_target(entry),
                    )
                )
            if entries:
                ProspectorFrontierEntry.objects.bulk_update(
                    entries,
                    [
                        "status",
                        "claim_token",
                        "claimed_by",
                        "claimed_at",
                        "lease_expires_at",
                        "completed_at",
                        "updated_at",
                    ],
                )
            return tuple(claims)

    async def claim(
        self,
        *,
        worker_id: str,
        limit: int,
        lease_seconds: int = 300,
    ) -> Sequence[FrontierClaim]:
        return await sync_to_async(self.claim_sync, thread_sensitive=True)(
            worker_id=worker_id,
            limit=limit,
            lease_seconds=lease_seconds,
        )

    def _claimed_entry(self, claim: FrontierClaim) -> ProspectorFrontierEntry:
        entry = _lock_queryset(
            ProspectorFrontierEntry.objects.filter(
                target_key=claim.target.target_key
            )
        ).first()
        if entry is None:
            raise FrontierClaimError("claimed target no longer exists")
        if entry.status != FrontierState.CLAIMED.value:
            raise FrontierClaimError("target is not currently claimed")
        if str(entry.claim_token) != claim.claim_token:
            raise FrontierClaimError("claim token is stale or belongs to another worker")
        if entry.claimed_by != claim.worker_id:
            raise FrontierClaimError("claim worker does not match durable owner")
        return entry

    def complete_sync(
        self,
        claim: FrontierClaim,
        *,
        now: Optional[datetime] = None,
    ) -> ProspectingTarget:
        now = _aware("now", now or timezone.now())
        with transaction.atomic():
            entry = self._claimed_entry(claim)
            entry.status = FrontierState.COMPLETED.value
            entry.claim_token = None
            entry.claimed_by = ""
            entry.claimed_at = None
            entry.lease_expires_at = None
            entry.completed_at = now
            entry.save(
                update_fields=[
                    "status",
                    "claim_token",
                    "claimed_by",
                    "claimed_at",
                    "lease_expires_at",
                    "completed_at",
                    "updated_at",
                ]
            )
            return _entry_target(entry)

    async def complete(self, claim: FrontierClaim) -> ProspectingTarget:
        return await sync_to_async(self.complete_sync, thread_sensitive=True)(claim)

    def defer_sync(
        self,
        claim: FrontierClaim,
        *,
        available_at: datetime,
    ) -> ProspectingTarget:
        available_at = _aware("available_at", available_at)
        with transaction.atomic():
            entry = self._claimed_entry(claim)
            entry.status = FrontierState.READY.value
            entry.available_at = available_at
            entry.claim_token = None
            entry.claimed_by = ""
            entry.claimed_at = None
            entry.lease_expires_at = None
            entry.completed_at = None
            entry.save(
                update_fields=[
                    "status",
                    "available_at",
                    "claim_token",
                    "claimed_by",
                    "claimed_at",
                    "lease_expires_at",
                    "completed_at",
                    "updated_at",
                ]
            )
            return _entry_target(entry)

    async def defer(
        self,
        claim: FrontierClaim,
        *,
        available_at: datetime,
    ) -> ProspectingTarget:
        return await sync_to_async(self.defer_sync, thread_sensitive=True)(
            claim,
            available_at=available_at,
        )

    def requeue_sync(
        self,
        *,
        target_key: str,
        available_at: Optional[datetime] = None,
    ) -> ProspectingTarget:
        target_key = _required_text("target_key", target_key, max_length=96)
        ready_at = _aware("available_at", available_at or timezone.now())
        with transaction.atomic():
            entry = _lock_queryset(
                ProspectorFrontierEntry.objects.filter(target_key=target_key)
            ).first()
            if entry is None:
                raise FrontierClaimError("target does not exist")
            if entry.status == FrontierState.CLAIMED.value:
                raise FrontierClaimError("cannot requeue a target owned by an active claim")
            entry.status = FrontierState.READY.value
            entry.available_at = ready_at
            entry.claim_token = None
            entry.claimed_by = ""
            entry.claimed_at = None
            entry.lease_expires_at = None
            entry.completed_at = None
            entry.save(
                update_fields=[
                    "status",
                    "available_at",
                    "claim_token",
                    "claimed_by",
                    "claimed_at",
                    "lease_expires_at",
                    "completed_at",
                    "updated_at",
                ]
            )
            return _entry_target(entry)

    async def requeue(
        self,
        *,
        target_key: str,
        available_at: Optional[datetime] = None,
    ) -> ProspectingTarget:
        return await sync_to_async(self.requeue_sync, thread_sensitive=True)(
            target_key=target_key,
            available_at=available_at,
        )
