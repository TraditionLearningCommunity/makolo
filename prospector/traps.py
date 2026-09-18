from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qsl, urlsplit, urlunsplit

from .canonicalization import canonicalize_web_url
from .errors import ProspectorContractError

_DATE_SEGMENT = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_UUID_SEGMENT = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-"
    r"[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)
_LONG_HEX_SEGMENT = re.compile(r"^[0-9a-fA-F]{16,}$")
_NUMERIC_SEGMENT = re.compile(r"^\d{2,}$")


@dataclass(frozen=True, slots=True)
class UrlStructure:
    canonical_locator: str
    host: str
    query_parameter_count: int
    path_segment_count: int
    shape: str


def _shape_segment(value: str) -> str:
    if _DATE_SEGMENT.fullmatch(value):
        return "{date}"
    if _UUID_SEGMENT.fullmatch(value):
        return "{uuid}"
    if _LONG_HEX_SEGMENT.fullmatch(value):
        return "{hex}"
    if _NUMERIC_SEGMENT.fullmatch(value):
        return "{n}"
    return value


def inspect_web_url(locator: str) -> UrlStructure:
    canonical = canonicalize_web_url(locator)
    parts = urlsplit(canonical)
    hostname = parts.hostname
    if not hostname:
        raise ProspectorContractError("canonical web URL must contain a hostname")

    segments = tuple(segment for segment in parts.path.split("/") if segment)
    shaped_segments = tuple(_shape_segment(segment) for segment in segments)
    shaped_path = "/" + "/".join(shaped_segments)
    if parts.path.endswith("/") and shaped_path != "/":
        shaped_path += "/"

    query_pairs = parse_qsl(parts.query, keep_blank_values=True)
    query_names = sorted({name.lower() for name, _value in query_pairs})
    shaped_query = "&".join(query_names)
    shape = urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            shaped_path or "/",
            shaped_query,
            "",
        )
    )

    return UrlStructure(
        canonical_locator=canonical,
        host=hostname.lower(),
        query_parameter_count=len(query_pairs),
        path_segment_count=len(segments),
        shape=shape,
    )
