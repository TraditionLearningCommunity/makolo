from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from django.db import connection, transaction
from django.db.models import Exists, OuterRef, Q
from django.db.models import Max
from django.utils import timezone

from prospector.observation_contracts import ObservationTarget

from .contracts import (
    AttemptLifecycle,
    AttemptOutcome,
    AttemptStrategy,
    ObservationLifecycle,
    ObservationOutcome,
    ObservationTrigger,
)
from .django_app.models import (
    Observation,
    ObservationAttempt,
    ObservationSeries,
    ObserverHandoff,
)
from .django_store import get_or_create_observation_series
from .errors import ObserverContractError, ObserverStateConflictError
from .ports import ObservationAcquisitionPort
from .runtime_contracts import (
    AcquisitionResult,
    ObservationBacklog,
    ObservationClaim,
    ObserverRuntimePolicy,
)


LEASE_EXPIRED_FAILURE = "runtime.lease_expired"
ACQUISITION_EXCEPTION_FAILURE = "runtime.acquisition_exception"


def _aware(name: str, value: datetime | None) -> datetime:
    value = value or timezone.now()
    if not isinstance(value, datetime) or timezone.is_naive(value):
        raise ObserverContractError(f"{name} must be timezone-aware")
    return value


def _positive_limit(value: int, *, name: str = "limit") -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ObserverContractError(f"{name} must be a positive integer")
    return value


def _lock_queryset(queryset, *, skip_locked: bool = False):
    if not connection.features.has_select_for_update:
        return queryset
    kwargs = {}
    if skip_locked and connection.features.has_select_for_update_skip_locked:
        kwargs["skip_locked"] = True
    return queryset.select_for_update(**kwargs)


def target_from_handoff(handoff: ObserverHandoff) -> ObservationTarget:
    return ObservationTarget(
        handoff_key=handoff.handoff_key,
        target_key=handoff.target_key,
        handoff_generation=handoff.handoff_generation,
        locator=handoff.locator,
        kind=handoff.kind,
        requested_at=handoff.requested_at,
        observation_hints=handoff.observation_hints,
        contract_version=handoff.contract_version,
    )


def _clear_due_if_started(series: ObservationSeries, *, now: datetime) -> None:
    fields = []
    if series.retry_due_at is not None and series.retry_due_at <= now:
        series.retry_due_at = None
        fields.append("retry_due_at")
    if series.watch_due_at is not None and series.watch_due_at <= now:
        series.watch_due_at = None
        fields.append("watch_due_at")
    if fields:
        fields.append("updated_at")
        series.save(update_fields=fields)


def _handoff_started_for_series(
    *,
    handoff: ObserverHandoff,
    series: ObservationSeries,
) -> bool:
    return Observation.objects.filter(
        source_handoff=handoff,
        series=series,
    ).exists()


def _pending_handoff_for_series(
    series: ObservationSeries,
) -> ObserverHandoff | None:
    started_for_series = Observation.objects.filter(
        source_handoff_id=OuterRef("pk"),
        series=series,
    )
    return (
        ObserverHandoff.objects.filter(
            target_key=series.target_key,
            kind=series.kind,
            locator=series.locator,
        )
        .annotate(started_for_series=Exists(started_for_series))
        .filter(started_for_series=False)
        .order_by("requested_at", "handoff_generation", "id")
        .first()
    )


def _latest_started_handoff(
    series: ObservationSeries,
) -> ObserverHandoff | None:
    return (
        ObserverHandoff.objects.filter(observations__series=series)
        .distinct()
        .order_by("-handoff_generation", "-requested_at", "-id")
        .first()
    )


def _pending_handoffs(policy: ObserverRuntimePolicy):
    started_for_profile = Observation.objects.filter(
        source_handoff_id=OuterRef("pk"),
        series__profile_fingerprint=policy.profile_fingerprint,
    )
    return (
        ObserverHandoff.objects.annotate(
            started_for_profile=Exists(started_for_profile),
        )
        .filter(started_for_profile=False)
        .order_by("requested_at", "handoff_generation", "id")
    )


def _actionable_handoffs(policy: ObserverRuntimePolicy):
    target_has_open_observation = Observation.objects.filter(
        series__target_key=OuterRef("target_key"),
        series__profile_fingerprint=policy.profile_fingerprint,
        lifecycle=ObservationLifecycle.OPEN.value,
    )
    return (
        _pending_handoffs(policy)
        .annotate(
            target_blocked_by_open=Exists(target_has_open_observation),
        )
        .filter(target_blocked_by_open=False)
    )


def _due_series(policy: ObserverRuntimePolicy, *, now: datetime):
    open_for_series = Observation.objects.filter(
        series_id=OuterRef("pk"),
        lifecycle=ObservationLifecycle.OPEN.value,
    )
    return (
        ObservationSeries.objects.filter(
            profile_fingerprint=policy.profile_fingerprint,
        )
        .filter(
            Q(retry_due_at__lte=now)
            | Q(watch_due_at__lte=now)
        )
        .annotate(has_open_observation=Exists(open_for_series))
        .filter(has_open_observation=False)
        .order_by("retry_due_at", "watch_due_at", "id")
    )


def observation_backlog(
    *,
    policy: ObserverRuntimePolicy,
    now: datetime | None = None,
) -> ObservationBacklog:
    """Read-only control-plane projection; never starts an Observation."""

    now = _aware("now", now)
    return ObservationBacklog(
        pending_handoffs=_pending_handoffs(policy).count(),
        due_retries=ObservationSeries.objects.filter(
            profile_fingerprint=policy.profile_fingerprint,
            retry_due_at__lte=now,
        ).count(),
        due_watches=ObservationSeries.objects.filter(
            profile_fingerprint=policy.profile_fingerprint,
            watch_due_at__lte=now,
        ).count(),
        open_observations=Observation.objects.filter(
            series__profile_fingerprint=policy.profile_fingerprint,
            lifecycle=ObservationLifecycle.OPEN.value,
        ).count(),
    )


def _claim_payload(
    observation: Observation,
    *,
    token: uuid.UUID,
    worker_id: str,
    leased_until: datetime,
) -> ObservationClaim:
    return ObservationClaim(
        observation_ref=observation.observation_ref,
        claim_token=str(token),
        worker_id=worker_id,
        leased_until=leased_until,
        target_key=observation.series.target_key,
        kind=observation.series.kind,
        locator=observation.requested_locator,
        source_handoff_key=observation.source_handoff.handoff_key,
        source_handoff_generation=(
            observation.source_handoff.handoff_generation
        ),
    )


def _create_claimed_observation(
    *,
    series: ObservationSeries,
    source_handoff: ObserverHandoff,
    trigger: ObservationTrigger,
    worker_id: str,
    policy: ObserverRuntimePolicy,
    now: datetime,
) -> ObservationClaim:
    token = uuid.uuid4()
    leased_until = now + timedelta(seconds=policy.lease_seconds)
    observation = Observation.objects.create(
        series=series,
        source_handoff=source_handoff,
        trigger=trigger.value,
        lifecycle=ObservationLifecycle.OPEN.value,
        started_at=now,
        requested_locator=series.locator,
        profile_ref=policy.profile_key,
        profile_fingerprint=policy.profile_fingerprint,
        policy_fingerprint=policy.policy_fingerprint,
        claim_token=token,
        claimed_by=worker_id,
        lease_expires_at=leased_until,
    )
    _clear_due_if_started(series, now=now)
    return _claim_payload(
        observation,
        token=token,
        worker_id=worker_id,
        leased_until=leased_until,
    )


@transaction.atomic
def _claim_handoff(
    handoff_id: int,
    *,
    worker_id: str,
    policy: ObserverRuntimePolicy,
    now: datetime,
) -> ObservationClaim | None:
    handoff = _lock_queryset(
        ObserverHandoff.objects.filter(pk=handoff_id),
        skip_locked=True,
    ).first()
    if handoff is None:
        return None

    target = target_from_handoff(handoff)
    series, _created = get_or_create_observation_series(
        target,
        profile_key=policy.profile_key,
        profile_fingerprint=policy.profile_fingerprint,
    )
    series = _lock_queryset(
        ObservationSeries.objects.filter(pk=series.pk),
        skip_locked=True,
    ).first()
    if series is None:
        return None
    if Observation.objects.filter(
        series=series,
        lifecycle=ObservationLifecycle.OPEN.value,
    ).exists():
        return None
    if _handoff_started_for_series(
        handoff=handoff,
        series=series,
    ):
        return None
    earliest_pending = _pending_handoff_for_series(series)
    if earliest_pending is None or earliest_pending.pk != handoff.pk:
        return None

    return _create_claimed_observation(
        series=series,
        source_handoff=handoff,
        trigger=ObservationTrigger.HANDOFF,
        worker_id=worker_id,
        policy=policy,
        now=now,
    )


@transaction.atomic
def _claim_series_due(
    series_id: int,
    *,
    worker_id: str,
    policy: ObserverRuntimePolicy,
    now: datetime,
) -> ObservationClaim | None:
    series = _lock_queryset(
        ObservationSeries.objects.filter(
            pk=series_id,
            profile_fingerprint=policy.profile_fingerprint,
        ),
        skip_locked=True,
    ).first()
    if series is None:
        return None
    if Observation.objects.filter(
        series=series,
        lifecycle=ObservationLifecycle.OPEN.value,
    ).exists():
        return None
    if _pending_handoff_for_series(series) is not None:
        return None

    retry_due = (
        series.retry_due_at is not None
        and series.retry_due_at <= now
    )
    watch_due = (
        series.watch_due_at is not None
        and series.watch_due_at <= now
    )
    if not retry_due and not watch_due:
        return None

    source_handoff = _latest_started_handoff(series)
    if source_handoff is None:
        return None
    trigger = (
        ObservationTrigger.RETRY
        if retry_due
        else ObservationTrigger.WATCH
    )
    return _create_claimed_observation(
        series=series,
        source_handoff=source_handoff,
        trigger=trigger,
        worker_id=worker_id,
        policy=policy,
        now=now,
    )


def claim_observations(
    *,
    worker_id: str,
    policy: ObserverRuntimePolicy,
    now: datetime | None = None,
    limit: int = 10,
) -> tuple[ObservationClaim, ...]:
    """Atomically start due observation episodes and lease them to a worker.

    Pending handoffs and series due-times are the durable scheduling state.
    Merely being due never creates an Observation. The historical Observation
    begins only when a worker actually claims the episode.
    """

    worker_id = (worker_id or "").strip()
    if not worker_id:
        raise ObserverContractError("worker_id must not be empty")
    now = _aware("now", now)
    limit = _positive_limit(limit)
    claims: list[ObservationClaim] = []

    # Explicit handoff generations always outrank autonomous retry/watch work.
    handoff_ids = list(
        _actionable_handoffs(policy)
        .values_list("id", flat=True)[: max(limit * 2, limit)]
    )
    for handoff_id in handoff_ids:
        if len(claims) >= limit:
            break
        claim = _claim_handoff(
            handoff_id,
            worker_id=worker_id,
            policy=policy,
            now=now,
        )
        if claim is not None:
            claims.append(claim)

    if len(claims) >= limit:
        return tuple(claims)

    due_series_ids = list(
        _due_series(policy, now=now)
        .values_list("id", flat=True)[
            : max((limit - len(claims)) * 2, limit)
        ]
    )
    for series_id in due_series_ids:
        if len(claims) >= limit:
            break
        claim = _claim_series_due(
            series_id,
            worker_id=worker_id,
            policy=policy,
            now=now,
        )
        if claim is not None:
            claims.append(claim)
    return tuple(claims)


@transaction.atomic
def recover_expired_observations(
    *,
    policy: ObserverRuntimePolicy,
    now: datetime | None = None,
    limit: int = 100,
) -> int:
    now = _aware("now", now)
    limit = _positive_limit(limit)
    queryset = Observation.objects.filter(
        lifecycle=ObservationLifecycle.OPEN.value,
        claim_token__isnull=False,
        lease_expires_at__lte=now,
    ).order_by("lease_expires_at", "id")
    expired = list(
        _lock_queryset(queryset, skip_locked=True)[:limit]
    )
    recovered = 0
    for observation in expired:
        ObservationAttempt.objects.filter(
            observation=observation,
            lifecycle=AttemptLifecycle.OPEN.value,
        ).update(
            lifecycle=AttemptLifecycle.FINALIZED.value,
            outcome=AttemptOutcome.INTERRUPTED.value,
            completed_at=now,
            failure_code=LEASE_EXPIRED_FAILURE,
        )
        retry_at = now + timedelta(
            seconds=policy.recovery_retry_seconds
        )
        observation.lifecycle = ObservationLifecycle.FINALIZED.value
        observation.outcome = ObservationOutcome.FAILED.value
        observation.observed_at = observation.observed_at or now
        observation.completed_at = now
        observation.failure_code = LEASE_EXPIRED_FAILURE
        observation.retry_at = retry_at
        observation.save(
            update_fields=[
                "lifecycle",
                "outcome",
                "observed_at",
                "completed_at",
                "failure_code",
                "retry_at",
                "updated_at",
            ]
        )

        series = _lock_queryset(
            ObservationSeries.objects.filter(pk=observation.series_id)
        ).get()
        if (
            series.retry_due_at is None
            or retry_at < series.retry_due_at
        ):
            series.retry_due_at = retry_at
            series.save(update_fields=["retry_due_at", "updated_at"])
        recovered += 1
    return recovered


@transaction.atomic
def _open_attempt_for_claim(
    claim: ObservationClaim,
    *,
    now: datetime,
    strategy: AttemptStrategy,
) -> ObservationAttempt:
    observation = _lock_queryset(
        Observation.objects.filter(
            observation_ref=claim.observation_ref,
        )
    ).select_related("series").first()
    if observation is None:
        raise ObserverStateConflictError("unknown claimed observation")
    if (
        observation.lifecycle != ObservationLifecycle.OPEN.value
        or str(observation.claim_token) != claim.claim_token
        or observation.claimed_by != claim.worker_id
    ):
        raise ObserverStateConflictError(
            "observation claim is no longer current"
        )
    if (
        observation.lease_expires_at is None
        or observation.lease_expires_at <= now
    ):
        raise ObserverStateConflictError(
            "observation claim lease has expired"
        )
    ordinal = (
        ObservationAttempt.objects.filter(observation=observation)
        .aggregate(value=Max("ordinal"))["value"]
        or 0
    ) + 1
    return ObservationAttempt.objects.create(
        observation=observation,
        ordinal=ordinal,
        strategy=AttemptStrategy(strategy).value,
        lifecycle=AttemptLifecycle.OPEN.value,
        started_at=now,
        requested_locator=observation.requested_locator,
    )


@transaction.atomic
def _finalize_claim(
    claim: ObservationClaim,
    *,
    attempt_id: int,
    result: AcquisitionResult,
    policy: ObserverRuntimePolicy,
    now: datetime,
) -> Observation:
    observation = _lock_queryset(
        Observation.objects.filter(
            observation_ref=claim.observation_ref,
        )
    ).select_related("series").first()
    if observation is None:
        raise ObserverStateConflictError("unknown claimed observation")
    if (
        observation.lifecycle != ObservationLifecycle.OPEN.value
        or str(observation.claim_token) != claim.claim_token
        or observation.claimed_by != claim.worker_id
    ):
        raise ObserverStateConflictError(
            "observation claim is no longer current"
        )
    if (
        observation.lease_expires_at is None
        or observation.lease_expires_at <= now
    ):
        raise ObserverStateConflictError(
            "observation claim lease expired before finalization"
        )

    attempt = _lock_queryset(
        ObservationAttempt.objects.filter(
            pk=attempt_id,
            observation=observation,
        )
    ).get()
    attempt.lifecycle = AttemptLifecycle.FINALIZED.value
    attempt.completed_at = now
    attempt.final_locator = result.final_locator or ""
    attempt.response_status = result.response_status
    if result.outcome is ObservationOutcome.FAILED:
        attempt.outcome = AttemptOutcome.FAILED.value
        attempt.failure_code = (
            result.failure_code
            or ACQUISITION_EXCEPTION_FAILURE
        )
    else:
        attempt.outcome = AttemptOutcome.SUCCEEDED.value
        attempt.failure_code = ""
    attempt.save(
        update_fields=[
            "lifecycle",
            "completed_at",
            "final_locator",
            "response_status",
            "outcome",
            "failure_code",
        ]
    )

    observation.lifecycle = ObservationLifecycle.FINALIZED.value
    observation.outcome = result.outcome.value
    observation.observed_at = result.observed_at
    observation.completed_at = now
    observation.final_locator = result.final_locator or ""
    observation.response_status = result.response_status
    observation.failure_code = result.failure_code or ""
    retry_at = result.retry_at
    if (
        result.outcome is ObservationOutcome.FAILED
        and retry_at is None
    ):
        retry_at = now + timedelta(
            seconds=policy.recovery_retry_seconds
        )
    observation.retry_at = retry_at
    observation.save(
        update_fields=[
            "lifecycle",
            "outcome",
            "observed_at",
            "completed_at",
            "final_locator",
            "response_status",
            "failure_code",
            "retry_at",
            "updated_at",
        ]
    )

    series = _lock_queryset(
        ObservationSeries.objects.filter(pk=observation.series_id)
    ).get()
    if result.outcome is ObservationOutcome.FAILED:
        if (
            series.retry_due_at is None
            or retry_at < series.retry_due_at
        ):
            series.retry_due_at = retry_at
            series.save(update_fields=["retry_due_at", "updated_at"])
    elif series.retry_due_at is not None:
        series.retry_due_at = None
        series.save(update_fields=["retry_due_at", "updated_at"])
    return observation


def execute_claim(
    claim: ObservationClaim,
    *,
    acquisition: ObservationAcquisitionPort,
    policy: ObserverRuntimePolicy,
    now: datetime | None = None,
    completed_at: datetime | None = None,
) -> Observation:
    started_at = _aware("now", now)
    try:
        strategy = AttemptStrategy(acquisition.strategy)
    except (AttributeError, ValueError) as exc:
        raise ObserverContractError(
            "acquisition port must declare a valid strategy"
        ) from exc
    attempt = _open_attempt_for_claim(
        claim,
        now=started_at,
        strategy=strategy,
    )
    unexpected_error = None
    try:
        result = acquisition.acquire(claim)
        if not isinstance(result, AcquisitionResult):
            raise ObserverContractError(
                "acquisition port must return AcquisitionResult"
            )
    except Exception as exc:
        unexpected_error = exc
        result = AcquisitionResult(
            outcome=ObservationOutcome.FAILED,
            observed_at=started_at,
            failure_code=ACQUISITION_EXCEPTION_FAILURE,
            retry_at=started_at
            + timedelta(seconds=policy.recovery_retry_seconds),
        )
    finished_at = _aware("completed_at", completed_at)
    observation = _finalize_claim(
        claim,
        attempt_id=attempt.pk,
        result=result,
        policy=policy,
        now=finished_at,
    )
    if unexpected_error is not None:
        raise unexpected_error
    return observation
