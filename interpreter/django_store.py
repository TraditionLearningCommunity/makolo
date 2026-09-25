from __future__ import annotations

from datetime import timedelta
from time import monotonic
from uuid import uuid4

from django.db import connection, transaction
from django.db.models import Count
from django.utils import timezone

from observer.contracts import ObservationLifecycle as ObserverLifecycle, make_material_key
from observer.django_app.models import Observation
from observer.django_artifacts import DjangoArtifactReader
from observer.django_material import DjangoObservationMaterialSource
from prospector.django_feedback import DjangoFeedbackStore
from prospector.feedback import FeedbackProducer, FeedbackSignal, ProspectingFeedback

from .contracts import ArtifactUse, InterpretedMaterial, InterpretationLifecycle, InterpretationOutcome, candidate_from_storage_payload, candidate_storage_payload
from .errors import InterpreterContractError
from .extraction import DeterministicInterpreter
from .identifiers import make_interpretation_ref
from .runtime_contracts import InterpretationClaim
from .django_app.models import InterpretationArtifactUse, InterpretationCandidate, InterpretationRun


def enqueue_interpretations(*, strategy=None, limit=100, observation_ref=None):
    strategy = strategy or DeterministicInterpreter()
    observations = Observation.objects.filter(lifecycle=ObserverLifecycle.FINALIZED.value).select_related("series")
    if observation_ref:
        observations = observations.filter(observation_ref=observation_ref)
    existing = InterpretationRun.objects.filter(strategy_fingerprint=strategy.strategy_fingerprint).values_list("observation_ref", flat=True)
    observations = observations.exclude(observation_ref__in=existing).order_by("completed_at", "id")[:max(int(limit), 1)]
    created = 0
    for observation in observations:
        material_key = make_material_key(observation_ref=observation.observation_ref)
        _run, new = InterpretationRun.objects.get_or_create(
            material_key=material_key,
            strategy_fingerprint=strategy.strategy_fingerprint,
            defaults={
                "interpretation_ref": make_interpretation_ref(material_key=material_key, strategy_fingerprint=strategy.strategy_fingerprint),
                "observation_ref": observation.observation_ref,
                "target_key": observation.series.target_key,
                "strategy_key": strategy.strategy_key,
                "strategy_version": strategy.strategy_version,
                "lifecycle": InterpretationLifecycle.PENDING.value,
            },
        )
        created += int(new)
    return created


@transaction.atomic
def recover_expired_interpretations(*, now=None):
    now = now or timezone.now()
    queryset = InterpretationRun.objects.filter(lifecycle="processing", lease_expires_at__lt=now).order_by("id")
    if connection.features.has_select_for_update:
        kwargs = {"of": ("self",)}
        if connection.features.has_select_for_update_skip_locked:
            kwargs["skip_locked"] = True
        queryset = queryset.select_for_update(**kwargs)
    rows = list(queryset[:1000])
    for run in rows:
        stats = dict(run.stats or {})
        stats["lease_recoveries"] = int(stats.get("lease_recoveries", 0)) + 1
        run.lifecycle = "pending"
        run.started_at = None
        run.claim_token = None
        run.claimed_by = ""
        run.lease_expires_at = None
        run.stats = stats
        run.updated_at = now
    if rows:
        InterpretationRun.objects.bulk_update(rows, ["lifecycle","started_at","claim_token","claimed_by","lease_expires_at","stats","updated_at"])
    return len(rows)


@transaction.atomic
def claim_interpretations(*, worker_id, limit, lease_seconds=300, strategy_fingerprint=None):
    worker_id = (worker_id or "").strip()
    if not worker_id:
        raise InterpreterContractError("worker_id is required")
    now = timezone.now()
    queryset = InterpretationRun.objects.filter(lifecycle="pending")
    if strategy_fingerprint:
        queryset = queryset.filter(strategy_fingerprint=strategy_fingerprint)
    queryset = queryset.order_by("created_at", "id")
    if connection.features.has_select_for_update:
        kwargs = {"of": ("self",)}
        if connection.features.has_select_for_update_skip_locked:
            kwargs["skip_locked"] = True
        queryset = queryset.select_for_update(**kwargs)
    claims = []
    for run in list(queryset[:max(int(limit), 1)]):
        token = uuid4()
        lease = now + timedelta(seconds=max(int(lease_seconds), 1))
        run.lifecycle = "processing"
        run.claim_token = token
        run.claimed_by = worker_id[:120]
        run.lease_expires_at = lease
        run.started_at = now
        run.save(update_fields=["lifecycle","claim_token","claimed_by","lease_expires_at","started_at","updated_at"])
        claims.append(InterpretationClaim(run.interpretation_ref, run.observation_ref, run.material_key, run.target_key, token, run.claimed_by, lease, now))
    return tuple(claims)


def _locked(claim):
    try:
        run = InterpretationRun.objects.select_for_update(of=("self",)).get(interpretation_ref=claim.interpretation_ref)
    except InterpretationRun.DoesNotExist as exc:
        raise InterpreterContractError("unknown interpretation claim") from exc
    if run.lifecycle != "processing" or run.claim_token != claim.claim_token or run.claimed_by != claim.claimed_by:
        raise InterpreterContractError("stale interpretation claim")
    if run.lease_expires_at is None or run.lease_expires_at <= timezone.now():
        raise InterpreterContractError("interpretation claim lease expired")
    return run


@transaction.atomic
def finalize_interpretation(claim, output, *, stats):
    run = _locked(claim)
    if (output.interpretation_ref, output.material_key, output.observation_ref, output.target_key) != (run.interpretation_ref, run.material_key, run.observation_ref, run.target_key):
        raise InterpreterContractError("output does not match claim")
    if output.strategy_fingerprint != run.strategy_fingerprint:
        raise InterpreterContractError("strategy changed during run")
    if run.candidate_rows.exists() or run.artifact_use_rows.exists():
        raise InterpreterContractError("processing run already owns output")
    InterpretationCandidate.objects.bulk_create([
        InterpretationCandidate(run=run, candidate_ref=item.candidate_ref, ordinal=i, kind=item.kind.value, payload=candidate_storage_payload(item))
        for i, item in enumerate(output.candidates, 1)
    ])
    InterpretationArtifactUse.objects.bulk_create([
        InterpretationArtifactUse(
            run=run, ordinal=i, artifact_ref=item.artifact_ref, artifact_observation_ref=item.artifact_observation_ref,
            role=item.role, media_type=item.media_type or "", content_digest=item.content_digest,
            selection_reason=item.selection_reason, completeness=item.completeness,
        )
        for i, item in enumerate(output.artifact_uses, 1)
    ])
    run.lifecycle = "finalized"
    run.outcome = output.outcome.value
    run.completed_at = output.completed_at
    run.failure_code = output.failure_code or ""
    run.warning_codes = list(output.warning_codes)
    run.stats = dict(stats)
    run.claim_token = None
    run.claimed_by = ""
    run.lease_expires_at = None
    run.save(update_fields=["lifecycle","outcome","completed_at","failure_code","warning_codes","stats","claim_token","claimed_by","lease_expires_at","updated_at"])
    return run


@transaction.atomic
def finalize_runtime_failure(claim, *, failure_code="parser_failure", warning_code="runtime_failure"):
    run = _locked(claim)
    run.lifecycle = "finalized"
    run.outcome = "failed"
    run.completed_at = timezone.now()
    run.failure_code = failure_code
    run.warning_codes = [warning_code]
    run.claim_token = None
    run.claimed_by = ""
    run.lease_expires_at = None
    run.save(update_fields=["lifecycle","outcome","completed_at","failure_code","warning_codes","claim_token","claimed_by","lease_expires_at","updated_at"])
    return run


def build_interpreted_material(interpretation_ref):
    try:
        run = InterpretationRun.objects.prefetch_related("candidate_rows","artifact_use_rows").get(interpretation_ref=(interpretation_ref or "").strip())
    except InterpretationRun.DoesNotExist as exc:
        raise InterpreterContractError("unknown interpretation_ref") from exc
    if run.lifecycle != "finalized":
        raise InterpreterContractError("only finalized interpretations can be projected")
    candidates = tuple(candidate_from_storage_payload(row.payload) for row in run.candidate_rows.all())
    uses = tuple(ArtifactUse(
        row.artifact_ref, row.artifact_observation_ref, row.role, row.media_type or None, row.content_digest, row.selection_reason, row.completeness
    ) for row in run.artifact_use_rows.all())
    return InterpretedMaterial(
        run.interpretation_ref, run.material_key, run.observation_ref, run.target_key,
        run.strategy_key, run.strategy_version, run.strategy_fingerprint,
        run.started_at, run.completed_at, InterpretationOutcome(run.outcome),
        candidates, uses, tuple(run.warning_codes or ()), run.failure_code or None,
    )


class DjangoInterpretedMaterialSource:
    def get_material(self, interpretation_ref):
        return build_interpreted_material(interpretation_ref)


def _feedback_key(run, signal):
    import hashlib
    return "interpreter-feedback:v1:" + hashlib.sha256(f"{run.interpretation_ref}\0{signal.value}".encode()).hexdigest()


def report_interpreter_feedback(run):
    if run.lifecycle != "finalized" or run.prospector_reported_at is not None:
        return False
    if run.outcome in {"interpreted","partial"}:
        signal = FeedbackSignal.STRUCTURED_INFORMATION
    elif run.outcome == "no_useful_information":
        signal = FeedbackSignal.NO_USEFUL_INFORMATION
    else:
        return False
    DjangoFeedbackStore().record_sync(ProspectingFeedback(
        event_key=_feedback_key(run, signal), target_key=run.target_key, signal=signal,
        producer=FeedbackProducer.INTERPRETER, source_ref=run.interpretation_ref, occurred_at=run.completed_at,
    ))
    InterpretationRun.objects.filter(pk=run.pk, prospector_reported_at__isnull=True).update(prospector_reported_at=timezone.now())
    return True


def report_pending_feedback(*, limit=100):
    rows = InterpretationRun.objects.filter(
        lifecycle="finalized", prospector_reported_at__isnull=True,
        outcome__in=["interpreted","partial","no_useful_information"],
    ).order_by("completed_at","id")[:max(int(limit), 1)]
    stats = {"reported": 0, "failed": 0}
    for run in rows:
        try:
            stats["reported"] += int(report_interpreter_feedback(run))
        except Exception:
            stats["failed"] += 1
    return stats


def interpreter_metrics():
    return {
        "runs": InterpretationRun.objects.count(),
        "lifecycle": {row["lifecycle"]: row["count"] for row in InterpretationRun.objects.values("lifecycle").annotate(count=Count("id"))},
        "outcomes": {row["outcome"]: row["count"] for row in InterpretationRun.objects.exclude(outcome="").values("outcome").annotate(count=Count("id"))},
        "candidates": InterpretationCandidate.objects.count(),
        "artifact_uses": InterpretationArtifactUse.objects.count(),
        "feedback_pending": InterpretationRun.objects.filter(lifecycle="finalized", prospector_reported_at__isnull=True).exclude(outcome="failed").count(),
    }


def process_interpretation_claim(claim, *, strategy=None, material_source=None, artifact_reader=None):
    strategy = strategy or DeterministicInterpreter()
    material_source = material_source or DjangoObservationMaterialSource()
    artifact_reader = artifact_reader or DjangoArtifactReader()
    started = monotonic()
    try:
        material = material_source.get_material(claim.observation_ref)
        output, stats = strategy.interpret(material, artifact_reader, started_at=claim.started_at, clock=timezone.now)
        stats = dict(stats)
        stats["duration_ms"] = max(int((monotonic() - started) * 1000), 0)
        run = finalize_interpretation(claim, output, stats=stats)
    except InterpreterContractError:
        raise
    except Exception:
        run = finalize_runtime_failure(claim)
    try:
        report_interpreter_feedback(run)
    except Exception:
        pass
    return run
