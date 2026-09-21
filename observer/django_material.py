from __future__ import annotations

from .contracts import (
    ArtifactCompleteness,
    ArtifactDescriptor,
    ArtifactOrigin,
    AttemptLifecycle,
    AttemptOutcome,
    AttemptStrategy,
    ObservationAttempt as ObservationAttemptContract,
    ObservationMaterial,
    ObservationOutcome,
    ObservationTrigger,
    TransformationDescriptor,
    make_material_key,
)
from .django_app.models import Observation
from .errors import ObserverContractError


def _artifact_descriptor(artifact) -> ArtifactDescriptor:
    transformation = None
    if artifact.transformation_name:
        transformation = TransformationDescriptor(
            name=artifact.transformation_name,
            version=artifact.transformation_version or None,
            fingerprint=artifact.transformation_fingerprint or None,
        )
    return ArtifactDescriptor(
        artifact_ref=artifact.artifact_ref,
        observation_ref=artifact.observation.observation_ref,
        producing_attempt_ref=(
            artifact.producing_attempt.attempt_ref
            if artifact.producing_attempt_id
            else None
        ),
        role=artifact.role,
        origin=ArtifactOrigin(artifact.origin),
        completeness=ArtifactCompleteness(artifact.completeness),
        declared_media_type=artifact.declared_media_type or None,
        detected_media_type=artifact.detected_media_type or None,
        charset=artifact.charset or None,
        byte_length=artifact.blob.byte_length,
        content_digest=artifact.blob.content_digest,
        captured_at=artifact.captured_at,
        source_artifact_ref=(
            artifact.source_artifact.artifact_ref
            if artifact.source_artifact_id
            else None
        ),
        transformation=transformation,
        protection_context_ref=artifact.protection_context_ref or None,
    )


def build_observation_material(
    observation_ref: str,
) -> ObservationMaterial:
    observation_ref = (observation_ref or "").strip()
    if not observation_ref:
        raise ObserverContractError(
            "observation_ref must not be empty"
        )
    try:
        observation = (
            Observation.objects.select_related(
                "series",
                "source_handoff",
            )
            .prefetch_related(
                "attempts",
                "revalidated_artifacts__blob",
                "revalidated_artifacts__observation",
                "revalidated_artifacts__producing_attempt",
                "revalidated_artifacts__source_artifact",
                "artifacts__blob",
                "artifacts__observation",
                "artifacts__producing_attempt",
                "artifacts__source_artifact",
            )
            .get(observation_ref=observation_ref)
        )
    except Observation.DoesNotExist as exc:
        raise ObserverContractError(
            "unknown observation_ref"
        ) from exc

    if observation.lifecycle != "finalized":
        raise ObserverContractError(
            "only finalized observations can be materialized"
        )

    attempts = tuple(
        ObservationAttemptContract(
            attempt_ref=attempt.attempt_ref,
            observation_ref=observation.observation_ref,
            ordinal=attempt.ordinal,
            strategy=AttemptStrategy(attempt.strategy),
            lifecycle=AttemptLifecycle(attempt.lifecycle),
            started_at=attempt.started_at,
            requested_locator=attempt.requested_locator,
            completed_at=attempt.completed_at,
            outcome=(
                AttemptOutcome(attempt.outcome)
                if attempt.outcome
                else None
            ),
            final_locator=attempt.final_locator or None,
            response_status=attempt.response_status,
            failure_code=attempt.failure_code or None,
            retry_after_at=attempt.retry_after_at,
            redirect_count=attempt.redirect_count,
            wire_bytes=attempt.wire_bytes,
            decoded_bytes=attempt.decoded_bytes,
        )
        for attempt in observation.attempts.all().order_by("ordinal")
    )

    descriptors = tuple(
        _artifact_descriptor(artifact)
        for artifact in observation.artifacts.all().order_by(
            "captured_at",
            "id",
        )
    )

    revalidated = list(
        observation.revalidated_artifacts
        .select_related(
            "observation__series",
            "blob",
            "producing_attempt",
            "source_artifact",
        )
        .order_by("artifact_ref")
    )
    for artifact in revalidated:
        if artifact.observation.series_id != observation.series_id:
            raise ObserverContractError(
                "revalidated artifact must belong to the same observation series"
            )
    revalidated_descriptors = tuple(
        _artifact_descriptor(artifact)
        for artifact in revalidated
    )

    return ObservationMaterial(
        material_key=make_material_key(
            observation_ref=observation.observation_ref
        ),
        observation_ref=observation.observation_ref,
        target_key=observation.series.target_key,
        target_kind=observation.series.kind,
        source_handoff_key=observation.source_handoff.handoff_key,
        source_handoff_generation=(
            observation.source_handoff.handoff_generation
        ),
        trigger=ObservationTrigger(observation.trigger),
        started_at=observation.started_at,
        observed_at=observation.observed_at,
        completed_at=observation.completed_at,
        requested_locator=observation.requested_locator,
        final_locator=observation.final_locator or None,
        observation_profile_ref=observation.profile_ref,
        observation_profile_fingerprint=(
            observation.profile_fingerprint
        ),
        policy_fingerprint=observation.policy_fingerprint,
        outcome=ObservationOutcome(observation.outcome),
        response_status=observation.response_status,
        failure_code=observation.failure_code or None,
        attempts=attempts,
        artifacts=descriptors,
        revalidated_artifacts=revalidated_descriptors,
    )
