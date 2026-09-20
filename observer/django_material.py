from __future__ import annotations

from .contracts import (
    ArtifactCompleteness,
    ArtifactDescriptor,
    ArtifactOrigin,
    ObservationMaterial,
    ObservationOutcome,
    TransformationDescriptor,
    make_material_key,
)
from .django_app.models import Observation
from .errors import ObserverContractError


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
                "revalidated_artifacts",
                "artifacts__blob",
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

    descriptors = []
    for artifact in observation.artifacts.all().order_by(
        "captured_at",
        "id",
    ):
        transformation = None
        if artifact.transformation_name:
            transformation = TransformationDescriptor(
                name=artifact.transformation_name,
                version=artifact.transformation_version or None,
                fingerprint=(
                    artifact.transformation_fingerprint or None
                ),
            )
        descriptors.append(
            ArtifactDescriptor(
                artifact_ref=artifact.artifact_ref,
                producing_attempt_ref=(
                    artifact.producing_attempt.attempt_ref
                    if artifact.producing_attempt_id
                    else None
                ),
                role=artifact.role,
                origin=ArtifactOrigin(artifact.origin),
                completeness=ArtifactCompleteness(
                    artifact.completeness
                ),
                declared_media_type=(
                    artifact.declared_media_type or None
                ),
                detected_media_type=(
                    artifact.detected_media_type or None
                ),
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
                protection_context_ref=(
                    artifact.protection_context_ref or None
                ),
            )
        )

    revalidated = list(
        observation.revalidated_artifacts
        .select_related("observation__series")
        .order_by("artifact_ref")
    )
    for artifact in revalidated:
        if artifact.observation.series_id != observation.series_id:
            raise ObserverContractError(
                "revalidated artifact must belong to the same observation series"
            )
    revalidated_refs = tuple(
        artifact.artifact_ref
        for artifact in revalidated
    )
    return ObservationMaterial(
        material_key=make_material_key(
            observation_ref=observation.observation_ref
        ),
        observation_ref=observation.observation_ref,
        target_key=observation.series.target_key,
        source_handoff_key=(
            observation.source_handoff.handoff_key
        ),
        source_handoff_generation=(
            observation.source_handoff.handoff_generation
        ),
        started_at=observation.started_at,
        completed_at=observation.completed_at,
        requested_locator=observation.requested_locator,
        final_locator=observation.final_locator or None,
        observation_profile_ref=observation.profile_ref,
        observation_profile_fingerprint=(
            observation.profile_fingerprint
        ),
        outcome=ObservationOutcome(observation.outcome),
        failure_code=observation.failure_code or None,
        artifacts=tuple(descriptors),
        revalidated_artifact_refs=revalidated_refs,
    )
