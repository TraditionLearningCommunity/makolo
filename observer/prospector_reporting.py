from __future__ import annotations

from asgiref.sync import sync_to_async
from django.db import transaction
from django.utils import timezone

from prospector.observation_contracts import (
    ObservationReport,
    ObservationStatus,
    ObservedReference,
)

from .contracts import ObservationOutcome
from .django_app.models import Observation
from .errors import ObserverContractError


_OUTCOME_TO_STATUS = {
    ObservationOutcome.OBSERVED.value: ObservationStatus.OBSERVED,
    ObservationOutcome.NOT_MODIFIED.value: ObservationStatus.NOT_MODIFIED,
    ObservationOutcome.FAILED.value: ObservationStatus.FAILED,
}


def build_observation_report(observation_ref: str) -> ObservationReport:
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
                "artifacts",
                "revalidated_artifacts",
                "observed_references",
                "attempts",
            )
            .get(observation_ref=observation_ref)
        )
    except Observation.DoesNotExist as exc:
        raise ObserverContractError(
            "unknown observation_ref"
        ) from exc

    if observation.lifecycle != "finalized":
        raise ObserverContractError(
            "only finalized observations can be reported"
        )
    try:
        status = _OUTCOME_TO_STATUS[observation.outcome]
    except KeyError as exc:
        raise ObserverContractError(
            "finalized observation has unsupported outcome"
        ) from exc

    media_type = None
    first_artifact = observation.artifacts.order_by(
        "captured_at",
        "id",
    ).first()
    if first_artifact is not None:
        media_type = (
            first_artifact.declared_media_type
            or first_artifact.detected_media_type
            or None
        )

    references = tuple(
        ObservedReference(
            relation=row.relation,
            locator=row.locator,
            discovered_at=row.discovered_at,
            kind=row.kind,
            attributes=row.attributes,
        )
        for row in observation.observed_references.order_by(
            "discovered_at",
            "id",
        )
    )

    attempts = list(observation.attempts.order_by("ordinal"))
    technical_metadata = {
        "attempt_count": len(attempts),
        "artifact_count": observation.artifacts.count(),
        "revalidated_artifact_count": (
            observation.revalidated_artifacts.count()
        ),
        "redirect_count": sum(
            attempt.redirect_count for attempt in attempts
        ),
        "wire_bytes": sum(
            attempt.wire_bytes for attempt in attempts
        ),
        "decoded_bytes": sum(
            attempt.decoded_bytes for attempt in attempts
        ),
    }
    if attempts:
        technical_metadata["strategy"] = attempts[-1].strategy

    return ObservationReport(
        handoff_key=observation.source_handoff.handoff_key,
        target_key=observation.series.target_key,
        handoff_generation=(
            observation.source_handoff.handoff_generation
        ),
        observation_ref=observation.observation_ref,
        status=status,
        observed_at=observation.observed_at,
        requested_locator=observation.requested_locator,
        final_locator=observation.final_locator or None,
        response_status=observation.response_status,
        media_type=media_type,
        references=references,
        failure_code=observation.failure_code or None,
        retry_at=observation.retry_at,
        technical_metadata=technical_metadata,
    )


@transaction.atomic
def mark_observation_reported(
    observation_ref: str,
    *,
    reported_at=None,
) -> bool:
    reported_at = reported_at or timezone.now()
    observation = (
        Observation.objects.select_for_update()
        .filter(observation_ref=observation_ref)
        .first()
    )
    if observation is None:
        raise ObserverContractError(
            "unknown observation_ref"
        )
    if observation.prospector_reported_at is not None:
        return False
    observation.prospector_reported_at = reported_at
    observation.save(
        update_fields=[
            "prospector_reported_at",
            "updated_at",
        ]
    )
    return True


async def submit_observation_report(
    observation_ref: str,
    *,
    sink,
) -> object:
    """Submit structure-only feedback and acknowledge only after sink success.

    A crash after sink success and before acknowledgement can replay the same
    report. The Prospecteur-side sink must therefore keep its own idempotent
    admission contract; Observer never marks a failed submission as reported.
    """

    report = await sync_to_async(
        build_observation_report,
        thread_sensitive=True,
    )(observation_ref)
    result = await sink.submit_report(report)
    await sync_to_async(
        mark_observation_reported,
        thread_sensitive=True,
    )(observation_ref)
    return result
