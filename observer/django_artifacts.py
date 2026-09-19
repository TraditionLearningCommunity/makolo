from __future__ import annotations

import hashlib

from django.core.files.base import ContentFile
from django.db import transaction

from .django_app.models import ObservedArtifact, ObserverBlob
from .errors import ArtifactStorageError


def _bytes(value) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    raise ArtifactStorageError(
        "artifact content must be bytes-like"
    )


@transaction.atomic
def store_blob(content) -> tuple[ObserverBlob, bool]:
    """Store bytes once by SHA-256 while logical artifacts stay distinct."""

    payload = _bytes(content)
    digest = hashlib.sha256(payload).hexdigest()
    blob = (
        ObserverBlob.objects.select_for_update()
        .filter(content_digest=digest)
        .first()
    )
    if blob is not None:
        if blob.byte_length != len(payload):
            raise ArtifactStorageError(
                "existing digest has inconsistent byte length"
            )
        if blob.purged_at is not None or not blob.file:
            raise ArtifactStorageError(
                "purged observer blob cannot be silently rehydrated"
            )
        return blob, False

    blob = ObserverBlob(
        content_digest=digest,
        byte_length=len(payload),
    )
    blob.full_clean(exclude=["file"])
    saved_name = None
    try:
        blob.file.save(
            "artifact.bin",
            ContentFile(payload),
            save=False,
        )
        saved_name = blob.file.name
        blob.full_clean()
        blob.save(force_insert=True)
    except Exception:
        if saved_name:
            blob.file.storage.delete(saved_name)
        raise
    return blob, True


def read_artifact_bytes(artifact_ref: str) -> bytes:
    artifact_ref = (artifact_ref or "").strip()
    if not artifact_ref:
        raise ArtifactStorageError(
            "artifact_ref must not be empty"
        )
    try:
        artifact = (
            ObservedArtifact.objects.select_related("blob")
            .get(artifact_ref=artifact_ref)
        )
    except ObservedArtifact.DoesNotExist as exc:
        raise ArtifactStorageError(
            "unknown artifact_ref"
        ) from exc
    blob = artifact.blob
    if blob.purged_at is not None or not blob.file:
        raise ArtifactStorageError(
            "artifact bytes are no longer retained"
        )
    try:
        with blob.file.open("rb") as handle:
            payload = handle.read()
    except OSError as exc:
        raise ArtifactStorageError(
            "artifact bytes are unavailable"
        ) from exc
    if len(payload) != blob.byte_length:
        raise ArtifactStorageError(
            "artifact byte length does not match durable metadata"
        )
    if hashlib.sha256(payload).hexdigest() != blob.content_digest:
        raise ArtifactStorageError(
            "artifact digest does not match durable metadata"
        )
    return payload
