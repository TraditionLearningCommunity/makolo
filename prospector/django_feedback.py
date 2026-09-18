from __future__ import annotations

import hashlib
import json
from typing import Mapping, Sequence

from asgiref.sync import sync_to_async
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone

from prospector.errors import FrontierConflictError, ProspectorContractError
from prospector.feedback import (
    AdaptivePolicy,
    CandidateLearning,
    FeedbackPolicy,
    FeedbackSignal,
    LearningScope,
    LearningStat,
    ProspectingFeedback,
    feedback_scopes_for_target,
    score_target,
)

from .django_app.models import (
    ProspectorFeedbackEvent,
    ProspectorFeedbackProjection,
    ProspectorFeedbackStat,
    ProspectorFrontierEntry,
)
from .django_frontier import _entry_target


def _lock_id(value: str) -> int:
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, byteorder="big", signed=True)


def _advisory_lock(value: str) -> None:
    if connection.vendor != "postgresql":
        return
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [_lock_id(value)])


def _serialize_scopes(scopes: Sequence[LearningScope]) -> list[dict[str, str]]:
    return [{"kind": scope.kind, "key": scope.key} for scope in scopes]


def _deserialize_scopes(value) -> tuple[LearningScope, ...]:
    if not isinstance(value, list):
        raise ProspectorContractError("stored feedback scopes must be a list")
    scopes = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ProspectorContractError("stored feedback scope must be a mapping")
        scopes.append(LearningScope(item.get("kind"), item.get("key")))
    return tuple(scopes)


class DjangoFeedbackStore:
    """Immutable downstream feedback log + rebuildable learning projection."""

    def record_sync(self, feedback: ProspectingFeedback) -> bool:
        if not isinstance(feedback, ProspectingFeedback):
            raise ProspectorContractError("feedback must be ProspectingFeedback")
        if len(feedback.event_key) > 160:
            raise ProspectorContractError("event_key exceeds maximum length 160")
        if len(feedback.target_key) > 96:
            raise ProspectorContractError("target_key exceeds maximum length 96")
        if len(feedback.source_ref) > 255:
            raise ProspectorContractError("source_ref exceeds maximum length 255")

        with transaction.atomic():
            _advisory_lock("feedback-event:" + feedback.event_key)
            existing = ProspectorFeedbackEvent.objects.filter(
                event_key=feedback.event_key
            ).first()
            if existing is not None:
                expected = {
                    "target_key": feedback.target_key,
                    "signal": feedback.signal.value,
                    "producer": feedback.producer.value,
                    "source_ref": feedback.source_ref,
                    "occurred_at": feedback.occurred_at,
                }
                actual = {
                    "target_key": existing.target_key,
                    "signal": existing.signal,
                    "producer": existing.producer,
                    "source_ref": existing.source_ref,
                    "occurred_at": existing.occurred_at,
                }
                if actual != expected:
                    raise FrontierConflictError(
                        "feedback event_key collision with different payload"
                    )
                return False

            entry = ProspectorFrontierEntry.objects.filter(
                target_key=feedback.target_key
            ).first()
            if entry is None:
                raise ProspectorContractError(
                    "feedback target must already exist in Frontier"
                )
            target = _entry_target(entry)
            scopes = feedback_scopes_for_target(target)
            ProspectorFeedbackEvent.objects.create(
                event_key=feedback.event_key,
                target_key=feedback.target_key,
                signal=feedback.signal.value,
                producer=feedback.producer.value,
                source_ref=feedback.source_ref,
                occurred_at=feedback.occurred_at,
                scopes=_serialize_scopes(scopes),
            )
            return True

    async def record(self, feedback: ProspectingFeedback) -> bool:
        return await sync_to_async(self.record_sync, thread_sensitive=True)(feedback)

    def refresh_sync(
        self,
        policy: FeedbackPolicy,
        *,
        batch_size: int,
    ) -> int:
        if not isinstance(policy, FeedbackPolicy):
            raise ProspectorContractError("policy must be FeedbackPolicy")
        if not isinstance(batch_size, int) or isinstance(batch_size, bool) or batch_size < 1:
            raise ProspectorContractError("batch_size must be a positive integer")

        with transaction.atomic():
            _advisory_lock(
                "feedback-projection:"
                + policy.policy_key
                + ":"
                + policy.fingerprint
            )
            projection, _created = ProspectorFeedbackProjection.objects.get_or_create(
                policy_key=policy.policy_key,
                policy_fingerprint=policy.fingerprint,
                defaults={"last_event_id": 0},
            )
            projection = ProspectorFeedbackProjection.objects.select_for_update().get(
                pk=projection.pk
            )
            events = list(
                ProspectorFeedbackEvent.objects.filter(
                    id__gt=projection.last_event_id
                ).order_by("id")[:batch_size]
            )
            if not events:
                return 0

            for event in events:
                try:
                    signal = FeedbackSignal(event.signal)
                except ValueError as exc:
                    raise ProspectorContractError(
                        f"stored feedback signal {event.signal!r} is invalid"
                    ) from exc
                weight = policy.weights[signal]
                for scope in _deserialize_scopes(event.scopes):
                    stat, _ = ProspectorFeedbackStat.objects.get_or_create(
                        policy_fingerprint=policy.fingerprint,
                        scope_kind=scope.kind,
                        scope_key=scope.key,
                        defaults={
                            "sample_count": 0,
                            "score_sum": 0,
                            "positive_count": 0,
                            "neutral_count": 0,
                            "negative_count": 0,
                            "last_feedback_at": event.occurred_at,
                        },
                    )
                    stat = ProspectorFeedbackStat.objects.select_for_update().get(
                        pk=stat.pk
                    )
                    stat.sample_count += 1
                    stat.score_sum += weight
                    if weight > 0:
                        stat.positive_count += 1
                    elif weight < 0:
                        stat.negative_count += 1
                    else:
                        stat.neutral_count += 1
                    stat.last_feedback_at = max(
                        stat.last_feedback_at,
                        event.occurred_at,
                    )
                    stat.save(
                        update_fields=[
                            "sample_count",
                            "score_sum",
                            "positive_count",
                            "neutral_count",
                            "negative_count",
                            "last_feedback_at",
                            "updated_at",
                        ]
                    )

            projection.last_event_id = events[-1].id
            projection.projected_at = timezone.now()
            projection.save(
                update_fields=[
                    "last_event_id",
                    "projected_at",
                    "updated_at",
                ]
            )
            return len(events)

    def refresh_all_sync(
        self,
        policy: FeedbackPolicy,
        *,
        batch_size: int,
    ) -> int:
        total = 0
        while True:
            processed = self.refresh_sync(policy, batch_size=batch_size)
            total += processed
            if processed < batch_size:
                return total

    async def refresh_all(
        self,
        policy: FeedbackPolicy,
        *,
        batch_size: int,
    ) -> int:
        return await sync_to_async(
            self.refresh_all_sync,
            thread_sensitive=True,
        )(policy, batch_size=batch_size)

    def learning_for_targets_sync(
        self,
        targets: Sequence,
        *,
        policy: AdaptivePolicy,
    ) -> dict[str, CandidateLearning]:
        targets = tuple(targets)
        scopes_by_target = {
            target.target_key: feedback_scopes_for_target(target)
            for target in targets
        }
        all_scopes = {
            scope
            for scopes in scopes_by_target.values()
            for scope in scopes
            if scope.kind in policy.dimension_weights
        }
        if not all_scopes:
            return {
                target.target_key: CandidateLearning(0, 0, 0)
                for target in targets
            }

        kinds = sorted({scope.kind for scope in all_scopes})
        keys = sorted({scope.key for scope in all_scopes})
        rows = ProspectorFeedbackStat.objects.filter(
            policy_fingerprint=policy.feedback.fingerprint,
            scope_kind__in=kinds,
            scope_key__in=keys,
        )
        stats = {}
        for row in rows:
            scope = LearningScope(row.scope_kind, row.scope_key)
            if scope not in all_scopes:
                continue
            stats[scope] = LearningStat(
                scope=scope,
                sample_count=row.sample_count,
                score_sum=row.score_sum,
            )

        return {
            target.target_key: score_target(
                target,
                stats=stats,
                policy=policy,
            )
            for target in targets
        }
