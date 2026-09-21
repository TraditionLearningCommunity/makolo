from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime

from django.utils import timezone


PROJECTION_SCHEMA_VERSION = 1
PERSONAL_PROJECTION_SCOPE = "personal"

_TECHNICAL_CODE_RE = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


class ProjectionContractError(ValueError):
    """Raised when a UX projection envelope violates the transversal contract."""


def _technical_code(value: str, *, field: str) -> str:
    value = (value or "").strip()
    if not _TECHNICAL_CODE_RE.fullmatch(value):
        raise ProjectionContractError(
            f"{field} doit etre un code technique stable en minuscules."
        )
    return value


def projection_meta(
    *,
    projection: str,
    generated_at: datetime | None = None,
    scope: str = PERSONAL_PROJECTION_SCOPE,
    schema_version: int = PROJECTION_SCHEMA_VERSION,
) -> dict:
    """Build metadata shared by Z UX projection endpoints.

    This helper carries transport metadata only. It deliberately does not rank,
    score, infer business state, authorize resources, or copy domain facts.
    """
    projection = _technical_code(projection, field="projection")
    scope = _technical_code(scope, field="scope")
    if (
        not isinstance(schema_version, int)
        or isinstance(schema_version, bool)
        or schema_version < 1
    ):
        raise ProjectionContractError("schema_version doit etre un entier positif.")

    generated_at = generated_at or timezone.now()
    if timezone.is_naive(generated_at):
        raise ProjectionContractError("generated_at doit inclure une timezone.")

    return {
        "projection": projection,
        "schema_version": schema_version,
        "generated_at": generated_at.isoformat(),
        "scope": scope,
    }


def projection_envelope(
    *,
    projection: str,
    data: Mapping,
    generated_at: datetime | None = None,
    scope: str = PERSONAL_PROJECTION_SCOPE,
    schema_version: int = PROJECTION_SCHEMA_VERSION,
) -> dict:
    """Wrap an already-authorized, already-composed projection in a stable envelope."""
    if not isinstance(data, Mapping):
        raise ProjectionContractError("data doit etre un objet de projection.")

    return {
        "meta": projection_meta(
            projection=projection,
            generated_at=generated_at,
            scope=scope,
            schema_version=schema_version,
        ),
        "data": dict(data),
    }
