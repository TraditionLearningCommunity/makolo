from __future__ import annotations

import hashlib

from django.core.files.base import ContentFile
from django.db import transaction

from .django_app.models import (
    ObservedArtifact,
    ObserverBlob,
    observer_blob_upload_to,
)
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


def _verify_payload(*, payload: bytes, digest: str) -> None:
    if hashlib.sha256(payload).hexdigest() != digest:
        raise ArtifactStorageError(
            "observer blob content does not match its digest"
        )


@transaction.atomic
def store_blob(content) -> tuple[ObserverBlob, bool]:
    """Store bytes once by SHA-256 while logical artifacts stay distinct.

    A matching orphaned file can be adopted after a crash that happened
    between durable file write and database commit. Conflicting bytes are
    never overwritten or silently renamed.
    """

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
    expected_name = observer_blob_upload_to(
        blob,
        "artifact.bin",
    )
    storage = blob.file.storage

    if storage.exists(expected_name):
        with storage.open(expected_name, "rb") as handle:
            existing_payload = handle.read()
        if len(existing_payload) != len(payload):
            raise ArtifactStorageError(
                "orphaned observer blob has inconsistent byte length"
            )
        _verify_payload(
            payload=existing_payload,
            digest=digest,
        )
        blob.file.name = expected_name
        blob.full_clean()
        blob.save(force_insert=True)
        return blob, True

    saved_name = storage.save(
        expected_name,
        ContentFile(payload),
    )
    if saved_name != expected_name:
        storage.delete(saved_name)
        raise ArtifactStorageError(
            "observer artifact storage refused content-addressed path"
        )

    blob.file.name = saved_name
    blob.full_clean()
    blob.save(force_insert=True)
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
    _verify_payload(
        payload=payload,
        digest=blob.content_digest,
    )
    return payload


class DjangoArtifactReader:
    """Private artifact reader used behind the Interpreter boundary."""

    def read(self, artifact_ref: str) -> bytes:
        return read_artifact_bytes(artifact_ref)
