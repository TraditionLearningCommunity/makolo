from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from .contracts import ProspectingCandidate, ProspectingEvidence
from .ports import ExternalIndexSourcePort, FrontierPort, SourceCheckpointPort
from .source_contracts import ProspectingMission, SourceCheckpoint, SourceRunResult


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


class IndexProspector:
    """Feeds external-index discoveries into the durable Frontier."""

    def __init__(
        self,
        *,
        frontier: FrontierPort,
        checkpoints: SourceCheckpointPort,
    ) -> None:
        self.frontier = frontier
        self.checkpoints = checkpoints

    async def run(
        self,
        *,
        source: ExternalIndexSourcePort,
        mission: ProspectingMission,
        now: Optional[datetime] = None,
    ) -> SourceRunResult:
        checkpoint = await self.checkpoints.load(
            source_name=source.name,
            mission_key=mission.mission_key,
            mission_fingerprint=mission.fingerprint,
        )
        batch = await source.discover(mission, checkpoint=checkpoint)

        admitted = 0
        for record in batch.records:
            evidence_attributes = {
                "source_revision": record.source_revision,
                "source_ref": record.source_ref,
            }
            if record.status_code is not None:
                evidence_attributes["status_code"] = record.status_code
            if record.registered_domain:
                evidence_attributes["registered_domain"] = record.registered_domain
            evidence_attributes.update(dict(record.attributes))

            observation_hints = {}
            if record.mime_type:
                observation_hints["indexed_mime_type"] = record.mime_type
            if record.language:
                observation_hints["indexed_language"] = record.language

            candidate = ProspectingCandidate(
                locator=record.locator,
                kind="web_url",
                evidence=(
                    ProspectingEvidence(
                        method="external_index",
                        discovered_at=record.observed_at,
                        provider=record.provider,
                        attributes=evidence_attributes,
                    ),
                ),
                policy_context={
                    "mission_key": mission.mission_key,
                    "mission_fingerprint": mission.fingerprint,
                    "source_name": source.name,
                    "mission_context": dict(mission.context),
                },
                observation_hints=observation_hints,
            )
            await self.frontier.admit(candidate)
            admitted += 1

        completed_at = now or _now_utc()
        next_checkpoint = SourceCheckpoint(
            source_name=batch.source_name,
            mission_key=mission.mission_key,
            mission_fingerprint=mission.fingerprint,
            source_revision=batch.source_revision,
            cursor=batch.next_cursor,
            exhausted=batch.exhausted,
            updated_at=completed_at,
        )
        # Cursor advancement is deliberately last. If admission fails midway,
        # the previous cursor remains durable and replay is safe because Frontier
        # admission is idempotent.
        await self.checkpoints.save(next_checkpoint)

        return SourceRunResult(
            source_name=batch.source_name,
            source_revision=batch.source_revision,
            received=len(batch.records),
            admitted=admitted,
            exhausted=batch.exhausted,
            next_cursor=batch.next_cursor,
        )
