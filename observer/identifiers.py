from __future__ import annotations

import hashlib
import uuid


def make_observation_ref() -> str:
    return f"observer:observation:v1:{uuid.uuid4()}"


def make_attempt_ref() -> str:
    return f"observer:attempt:v1:{uuid.uuid4()}"


def make_artifact_ref() -> str:
    return f"observer:artifact:v1:{uuid.uuid4()}"


def make_reference_key(*, relation: str, kind: str, locator: str) -> str:
    payload = f"{relation.strip()}\0{kind.strip()}\0{locator.strip()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()
