from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional, Sequence

from asgiref.sync import sync_to_async
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from prospector.errors import ProspectorContractError
from prospector.feedback import AdaptivePolicy
from prospector.frontier import FrontierClaim, FrontierState

from .django_feedback import DjangoFeedbackStore
from .django_frontier import (
    MAX_CLAIM_BATCH,
    MAX_LEASE_SECONDS,
    DjangoFrontierStore,
    _aware,
    _entry_target,
    _lock_queryset,
    _required_text,
)
from .django_app.models import ProspectorFrontierEntry


class DjangoAdaptiveFrontierStore(DjangoFrontierStore):
    """Frontier adapter reserving exploration while exploiting learned yield.

    Existing Frontier priority/availability first bounds the candidate pool.
    Learning only reorders that bounded pool; it never overrides hard gates.
    """

    def __init__(
        self,
        *,
        feedback_store: DjangoFeedbackStore,
        policy: AdaptivePolicy,
    ) -> None:
        self.feedback_store = feedback_store
        self.adaptive_policy = policy

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
            raise ProspectorContractError(
                "limit and lease_seconds must be integers"
            ) from exc
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

        self.feedback_store.refresh_all_sync(
            self.adaptive_policy.feedback,
            batch_size=self.adaptive_policy.projection_batch_size,
        )

        pool_size = min(
            MAX_CLAIM_BATCH,
            max(
                limit,
                limit * self.adaptive_policy.candidate_pool_multiplier,
            ),
        )
        eligible = (
            Q(
                status=FrontierState.READY.value,
                available_at__lte=now,
            )
            | Q(
                status=FrontierState.CLAIMED.value,
                lease_expires_at__lte=now,
            )
        )

        # Ranking is a snapshot, not a lock. Locking the whole candidate pool
        # would make concurrent workers skip useful rows that this worker will
        # never claim. Final eligibility is revalidated under a row lock below.
        pool = list(
            ProspectorFrontierEntry.objects.filter(eligible)
            .order_by("priority", "available_at", "id")[:pool_size]
        )
        if not pool:
            return ()

        targets = [_entry_target(entry) for entry in pool]
        learning = self.feedback_store.learning_for_targets_sync(
            targets,
            policy=self.adaptive_policy,
        )
        target_by_entry = {
            entry.pk: target
            for entry, target in zip(pool, targets)
        }

        exploration = []
        exploitation = []
        for entry in pool:
            target = target_by_entry[entry.pk]
            learned = learning[target.target_key]
            item = (entry, target, learned)
            if (
                learned.support_samples
                < self.adaptive_policy.min_samples_for_exploitation
            ):
                exploration.append(item)
            else:
                exploitation.append(item)

        exploration.sort(
            key=lambda item: (
                item[2].support_samples,
                item[0].priority,
                item[0].available_at,
                item[0].id,
            )
        )
        exploitation.sort(
            key=lambda item: (
                -item[2].mean_score,
                item[0].priority,
                item[0].available_at,
                item[0].id,
            )
        )

        exploration_slots = self.adaptive_policy.exploration_slots(limit)
        with transaction.atomic():
            selected = []
            selected_ids = set()

            def try_add(item) -> bool:
                entry, _snapshot_target, learned = item
                if entry.pk in selected_ids or len(selected) >= limit:
                    return False
                locked = _lock_queryset(
                    ProspectorFrontierEntry.objects.filter(
                        Q(pk=entry.pk) & eligible
                    ),
                    skip_locked=True,
                ).first()
                if locked is None:
                    return False
                selected.append((locked, _entry_target(locked), learned))
                selected_ids.add(locked.pk)
                return True

            explored = 0
            for item in exploration:
                if explored >= exploration_slots:
                    break
                if try_add(item):
                    explored += 1

            for item in exploitation:
                if len(selected) >= limit:
                    break
                try_add(item)

            if len(selected) < limit:
                for item in exploration:
                    if len(selected) >= limit:
                        break
                    try_add(item)

            if len(selected) < limit:
                for item in exploitation:
                    if len(selected) >= limit:
                        break
                    try_add(item)

            claims = []
            entries = []
            for entry, target, _learned in selected:
                token = uuid.uuid4()
                entry.status = FrontierState.CLAIMED.value
                entry.claim_token = token
                entry.claimed_by = worker_id
                entry.claimed_at = now
                entry.lease_expires_at = leased_until
                entry.completed_at = None
                entries.append(entry)
                claims.append(
                    FrontierClaim(
                        claim_token=str(token),
                        worker_id=worker_id,
                        leased_until=leased_until,
                        target=target,
                        handoff_generation=entry.handoff_generation,
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
