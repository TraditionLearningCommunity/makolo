from __future__ import annotations

from datetime import timedelta
from time import monotonic
from uuid import uuid4

from django.db import connection, transaction
from django.db.models import Count
from django.utils import timezone

from interpreter.contracts import InterpretationOutcome
from interpreter.django_app.models import InterpretationRun
from interpreter.django_store import DjangoInterpretedMaterialSource
from prospector.django_feedback import DjangoFeedbackStore
from prospector.feedback import FeedbackProducer, FeedbackSignal, ProspectingFeedback

from .contracts import (
    CanonicalRef,
    ResolvedMaterial,
    ResolutionAssertion,
    ResolutionLifecycle,
    ResolutionOutcome,
    ResolutionStatus,
)
from .django_catalog import DjangoRealityCatalog
from .django_history import DjangoResolutionHistory
from .errors import ResolverContractError
from .identifiers import make_resolution_ref
from .normalization import endpoint_key
from .runtime_contracts import ResolutionClaim
from .strategy import DeterministicResolver
from .django_app.models import ResolutionAssertionRow, ResolutionRun


def enqueue_resolutions(*, strategy=None, limit=100, interpretation_ref=None):
    strategy = strategy or DeterministicResolver()
    interpretations = InterpretationRun.objects.filter(
        lifecycle="finalized",
        outcome__in=[InterpretationOutcome.INTERPRETED.value, InterpretationOutcome.PARTIAL.value],
    )
    if interpretation_ref:
        interpretations = interpretations.filter(interpretation_ref=interpretation_ref)
    existing = ResolutionRun.objects.filter(
        strategy_fingerprint=strategy.strategy_fingerprint
    ).values_list("interpretation_ref", flat=True)
    interpretations = interpretations.exclude(interpretation_ref__in=existing).order_by("completed_at", "id")[:max(int(limit), 1)]
    created = 0
    for interpretation in interpretations:
        _run, new = ResolutionRun.objects.get_or_create(
            interpretation_ref=interpretation.interpretation_ref,
            strategy_fingerprint=strategy.strategy_fingerprint,
            defaults={
                "resolution_ref": make_resolution_ref(
                    interpretation_ref=interpretation.interpretation_ref,
                    strategy_fingerprint=strategy.strategy_fingerprint,
                ),
                "material_key": interpretation.material_key,
                "observation_ref": interpretation.observation_ref,
                "target_key": interpretation.target_key,
                "strategy_key": strategy.strategy_key,
                "strategy_version": strategy.strategy_version,
                "lifecycle": ResolutionLifecycle.PENDING.value,
            },
        )
        created += int(new)
    return created


@transaction.atomic
def recover_expired_resolutions(*, now=None):
    now = now or timezone.now()
    queryset = ResolutionRun.objects.filter(
        lifecycle=ResolutionLifecycle.PROCESSING.value,
        lease_expires_at__lt=now,
    ).order_by("id")
    if connection.features.has_select_for_update:
        kwargs = {"of": ("self",)}
        if connection.features.has_select_for_update_skip_locked:
            kwargs["skip_locked"] = True
        queryset = queryset.select_for_update(**kwargs)
    rows = list(queryset[:1000])
    for run in rows:
        stats = dict(run.stats or {})
        stats["lease_recoveries"] = int(stats.get("lease_recoveries", 0)) + 1
        run.lifecycle = ResolutionLifecycle.PENDING.value
        run.started_at = None
        run.claim_token = None
        run.claimed_by = ""
        run.lease_expires_at = None
        run.stats = stats
        run.updated_at = now
    if rows:
        ResolutionRun.objects.bulk_update(
            rows,
            [
                "lifecycle",
                "started_at",
                "claim_token",
                "claimed_by",
                "lease_expires_at",
                "stats",
                "updated_at",
            ],
        )
    return len(rows)


@transaction.atomic
def claim_resolutions(*, worker_id, limit, lease_seconds=300):
    worker_id = (worker_id or "").strip()
    if not worker_id:
        raise ResolverContractError("worker_id is required")
    now = timezone.now()
    queryset = ResolutionRun.objects.filter(lifecycle=ResolutionLifecycle.PENDING.value).order_by("created_at", "id")
    if connection.features.has_select_for_update:
        kwargs = {"of": ("self",)}
        if connection.features.has_select_for_update_skip_locked:
            kwargs["skip_locked"] = True
        queryset = queryset.select_for_update(**kwargs)
    claims = []
    for run in list(queryset[:max(int(limit), 1)]):
        token = uuid4()
        lease = now + timedelta(seconds=max(int(lease_seconds), 1))
        run.lifecycle = ResolutionLifecycle.PROCESSING.value
        run.claim_token = token
        run.claimed_by = worker_id[:120]
        run.lease_expires_at = lease
        run.started_at = now
        run.save(
            update_fields=[
                "lifecycle",
                "claim_token",
                "claimed_by",
                "lease_expires_at",
                "started_at",
                "updated_at",
            ]
        )
        claims.append(
            ResolutionClaim(
                run.resolution_ref,
                run.interpretation_ref,
                run.material_key,
                run.target_key,
                token,
                run.claimed_by,
                lease,
                now,
            )
        )
    return tuple(claims)


def _locked(claim):
    try:
        run = ResolutionRun.objects.select_for_update(of=("self",)).get(
            resolution_ref=claim.resolution_ref
        )
    except ResolutionRun.DoesNotExist as exc:
        raise ResolverContractError("unknown resolution claim") from exc
    if (
        run.lifecycle != ResolutionLifecycle.PROCESSING.value
        or run.claim_token != claim.claim_token
        or run.claimed_by != claim.claimed_by
    ):
        raise ResolverContractError("stale resolution claim")
    if run.lease_expires_at is None or run.lease_expires_at <= timezone.now():
        raise ResolverContractError("resolution claim lease expired")
    return run


@transaction.atomic
def finalize_resolution(claim, output, *, stats):
    run = _locked(claim)
    if (
        output.resolution_ref,
        output.interpretation_ref,
        output.material_key,
        output.target_key,
    ) != (
        run.resolution_ref,
        run.interpretation_ref,
        run.material_key,
        run.target_key,
    ):
        raise ResolverContractError("output does not match claim")
    if output.strategy_fingerprint != run.strategy_fingerprint:
        raise ResolverContractError("strategy changed during run")
    if run.assertion_rows.exists():
        raise ResolverContractError("processing run already owns output")

    rows = []
    for ordinal, assertion in enumerate(output.assertions, 1):
        canonical = assertion.canonical_ref
        rows.append(
            ResolutionAssertionRow(
                run=run,
                assertion_ref=assertion.assertion_ref,
                ordinal=ordinal,
                candidate_ref=assertion.candidate_ref,
                kind=assertion.kind.value,
                status=assertion.status.value,
                canonical_domain=canonical.domain if canonical else "",
                canonical_object_ref=canonical.object_ref if canonical else "",
                predicate=assertion.predicate or "",
                subject_key=endpoint_key(assertion.subject),
                object_key=endpoint_key(assertion.object),
                semantic_fingerprint=assertion.semantic_fingerprint or "",
                payload=assertion.to_payload(),
            )
        )
    ResolutionAssertionRow.objects.bulk_create(rows)

    run.lifecycle = ResolutionLifecycle.FINALIZED.value
    run.outcome = output.outcome.value
    run.completed_at = output.completed_at
    run.failure_code = output.failure_code or ""
    run.warning_codes = list(output.warning_codes)
    merged_stats = dict(run.stats or {})
    merged_stats.update(dict(stats))
    run.stats = merged_stats
    run.claim_token = None
    run.claimed_by = ""
    run.lease_expires_at = None
    run.save(
        update_fields=[
            "lifecycle",
            "outcome",
            "completed_at",
            "failure_code",
            "warning_codes",
            "stats",
            "claim_token",
            "claimed_by",
            "lease_expires_at",
            "updated_at",
        ]
    )
    return run


@transaction.atomic
def requeue_resolution_claim(claim, *, warning_code="canonical_changed_during_resolution", max_retries=3):
    run = _locked(claim)
    stats = dict(run.stats or {})
    retries = int(stats.get("stale_candidate_retries", 0)) + 1
    stats["stale_candidate_retries"] = retries
    warnings = list(run.warning_codes or [])
    if warning_code not in warnings:
        warnings.append(warning_code)
    if retries >= max_retries:
        run.lifecycle = ResolutionLifecycle.FINALIZED.value
        run.outcome = ResolutionOutcome.FAILED.value
        run.completed_at = timezone.now()
        run.failure_code = "backend_changed"
    else:
        run.lifecycle = ResolutionLifecycle.PENDING.value
        run.started_at = None
    run.warning_codes = warnings
    run.stats = stats
    run.claim_token = None
    run.claimed_by = ""
    run.lease_expires_at = None
    run.save(
        update_fields=[
            "lifecycle",
            "outcome",
            "started_at",
            "completed_at",
            "failure_code",
            "warning_codes",
            "stats",
            "claim_token",
            "claimed_by",
            "lease_expires_at",
            "updated_at",
        ]
    )
    return run


@transaction.atomic
def finalize_runtime_failure(claim, *, failure_code="strategy_failure", warning_code="runtime_failure"):
    run = _locked(claim)
    run.lifecycle = ResolutionLifecycle.FINALIZED.value
    run.outcome = ResolutionOutcome.FAILED.value
    run.completed_at = timezone.now()
    run.failure_code = failure_code
    run.warning_codes = [warning_code]
    run.claim_token = None
    run.claimed_by = ""
    run.lease_expires_at = None
    run.save(
        update_fields=[
            "lifecycle",
            "outcome",
            "completed_at",
            "failure_code",
            "warning_codes",
            "claim_token",
            "claimed_by",
            "lease_expires_at",
            "updated_at",
        ]
    )
    return run


def build_resolved_material(resolution_ref):
    try:
        run = ResolutionRun.objects.prefetch_related("assertion_rows").get(
            resolution_ref=(resolution_ref or "").strip()
        )
    except ResolutionRun.DoesNotExist as exc:
        raise ResolverContractError("unknown resolution_ref") from exc
    if run.lifecycle != ResolutionLifecycle.FINALIZED.value:
        raise ResolverContractError("only finalized resolutions can be projected")
    assertions = tuple(
        ResolutionAssertion.from_payload(row.payload)
        for row in run.assertion_rows.all()
    )
    return ResolvedMaterial(
        resolution_ref=run.resolution_ref,
        interpretation_ref=run.interpretation_ref,
        material_key=run.material_key,
        observation_ref=run.observation_ref,
        target_key=run.target_key,
        strategy_key=run.strategy_key,
        strategy_version=run.strategy_version,
        strategy_fingerprint=run.strategy_fingerprint,
        started_at=run.started_at,
        completed_at=run.completed_at,
        outcome=ResolutionOutcome(run.outcome),
        assertions=assertions,
        warning_codes=tuple(run.warning_codes or ()),
        failure_code=run.failure_code or None,
    )


class DjangoResolvedMaterialSource:
    def get_material(self, resolution_ref):
        return build_resolved_material(resolution_ref)


def _feedback_key(run, signal):
    import hashlib

    return "resolver-feedback:v1:" + hashlib.sha256(
        f"{run.resolution_ref}\0{signal.value}".encode()
    ).hexdigest()


def _feedback_signals(run):
    rows = run.assertion_rows.all()
    statuses = set(rows.values_list("status", flat=True))
    signals = []
    if rows.filter(kind="entity", status=ResolutionStatus.NEW_CANDIDATE.value).exists():
        signals.append(FeedbackSignal.REALITY_NEW)
    if (
        rows.filter(kind="entity", status=ResolutionStatus.MATCHED.value).exists()
        or ResolutionStatus.UPDATE.value in statuses
    ):
        signals.append(FeedbackSignal.REALITY_REFRESHED)
    if ResolutionStatus.REJECTED.value in statuses:
        signals.append(FeedbackSignal.DOWNSTREAM_REJECTED)
    return tuple(signals)


def report_resolver_feedback(run):
    if run.lifecycle != ResolutionLifecycle.FINALIZED.value or run.prospector_reported_at is not None:
        return 0
    signals = _feedback_signals(run)
    for signal in signals:
        DjangoFeedbackStore().record_sync(
            ProspectingFeedback(
                event_key=_feedback_key(run, signal),
                target_key=run.target_key,
                signal=signal,
                producer=FeedbackProducer.RESOLVER,
                source_ref=run.resolution_ref,
                occurred_at=run.completed_at,
            )
        )
    ResolutionRun.objects.filter(
        pk=run.pk,
        prospector_reported_at__isnull=True,
    ).update(prospector_reported_at=timezone.now())
    return len(signals)


def report_pending_feedback(*, limit=100):
    rows = ResolutionRun.objects.filter(
        lifecycle=ResolutionLifecycle.FINALIZED.value,
        prospector_reported_at__isnull=True,
    ).exclude(outcome=ResolutionOutcome.FAILED.value).order_by("completed_at", "id")[:max(int(limit), 1)]
    stats = {"reported": 0, "failed": 0}
    for run in rows:
        try:
            stats["reported"] += report_resolver_feedback(run)
        except Exception:
            stats["failed"] += 1
    return stats


def resolver_metrics():
    return {
        "runs": ResolutionRun.objects.count(),
        "lifecycle": {
            row["lifecycle"]: row["count"]
            for row in ResolutionRun.objects.values("lifecycle").annotate(count=Count("id"))
        },
        "outcomes": {
            row["outcome"]: row["count"]
            for row in ResolutionRun.objects.exclude(outcome="").values("outcome").annotate(count=Count("id"))
        },
        "assertions": ResolutionAssertionRow.objects.count(),
        "feedback_pending": ResolutionRun.objects.filter(
            lifecycle=ResolutionLifecycle.FINALIZED.value,
            prospector_reported_at__isnull=True,
        ).exclude(outcome=ResolutionOutcome.FAILED.value).count(),
    }


def process_resolution_claim(claim, *, strategy=None, material_source=None, catalog=None, history=None):
    strategy = strategy or DeterministicResolver()
    material_source = material_source or DjangoInterpretedMaterialSource()
    catalog = catalog or DjangoRealityCatalog()
    history = history or DjangoResolutionHistory()
    started = monotonic()
    try:
        material = material_source.get_material(claim.interpretation_ref)
        output, stats = strategy.resolve(
            material,
            catalog,
            history,
            started_at=claim.started_at,
            clock=timezone.now,
        )
        if hasattr(catalog, "validate_output") and not catalog.validate_output(output):
            return requeue_resolution_claim(claim)
        stats = dict(stats)
        stats["duration_ms"] = max(int((monotonic() - started) * 1000), 0)
        run = finalize_resolution(claim, output, stats=stats)
    except ResolverContractError:
        run = finalize_runtime_failure(claim, failure_code="contract_error", warning_code="contract_error")
    except Exception:
        run = finalize_runtime_failure(claim)
    if run.lifecycle == ResolutionLifecycle.FINALIZED.value:
        try:
            report_resolver_feedback(run)
        except Exception:
            pass
    return run
