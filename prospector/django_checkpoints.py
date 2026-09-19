from __future__ import annotations

from typing import Optional

from asgiref.sync import sync_to_async
from django.db import transaction

from prospector.source_contracts import SourceCheckpoint

from .django_app.models import ProspectorSourceCheckpoint


class DjangoSourceCheckpointStore:
    """Durable provider cursor storage behind the framework-free port."""

    def load_sync(
        self,
        *,
        source_name: str,
        mission_key: str,
        mission_fingerprint: str,
    ) -> Optional[SourceCheckpoint]:
        row = ProspectorSourceCheckpoint.objects.filter(
            source_name=source_name,
            mission_key=mission_key,
            mission_fingerprint=mission_fingerprint,
        ).first()
        if row is None:
            return None
        return SourceCheckpoint(
            source_name=row.source_name,
            mission_key=row.mission_key,
            mission_fingerprint=row.mission_fingerprint,
            source_revision=row.source_revision,
            cursor=row.cursor,
            exhausted=row.exhausted,
            updated_at=row.checkpoint_updated_at,
        )

    async def load(
        self,
        *,
        source_name: str,
        mission_key: str,
        mission_fingerprint: str,
    ) -> Optional[SourceCheckpoint]:
        return await sync_to_async(self.load_sync, thread_sensitive=True)(
            source_name=source_name,
            mission_key=mission_key,
            mission_fingerprint=mission_fingerprint,
        )

    def save_sync(self, checkpoint: SourceCheckpoint) -> None:
        with transaction.atomic():
            ProspectorSourceCheckpoint.objects.update_or_create(
                source_name=checkpoint.source_name,
                mission_key=checkpoint.mission_key,
                defaults={
                    "mission_fingerprint": checkpoint.mission_fingerprint,
                    "source_revision": checkpoint.source_revision,
                    "cursor": dict(checkpoint.cursor),
                    "exhausted": checkpoint.exhausted,
                    "checkpoint_updated_at": checkpoint.updated_at,
                },
            )

    async def save(self, checkpoint: SourceCheckpoint) -> None:
        await sync_to_async(self.save_sync, thread_sensitive=True)(checkpoint)
