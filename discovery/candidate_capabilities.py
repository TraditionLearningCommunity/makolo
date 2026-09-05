from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CandidateFilterCapabilities:
    """Read-only contract for filters a Discovery candidate family can prove."""

    family: str
    supported_filters: frozenset[str]

    def unsupported_filters(self, params) -> tuple[str, ...]:
        active = active_filter_keys(params)
        return tuple(sorted(active - self.supported_filters))

    def can_satisfy(self, params) -> bool:
        return not self.unsupported_filters(params)


# Occurrence owns temporal/spatial execution and may therefore interpret the
# complete current Discovery filter vocabulary. Service and Opportunity are
# deliberately conservative until their domains expose canonical selectors for
# additional semantics.
OCCURRENCE_FILTER_CAPABILITIES = CandidateFilterCapabilities(
    family="occurrence",
    supported_filters=frozenset(
        {
            "q",
            "place",
            "when",
            "period",
            "vertical",
            "price",
            "proximity",
            "date",
            "date_from",
            "date_to",
            "ordering",
            "timezone",
        }
    ),
)
SERVICE_FILTER_CAPABILITIES = CandidateFilterCapabilities(
    family="service",
    supported_filters=frozenset({"q", "vertical", "timezone"}),
)
OPPORTUNITY_FILTER_CAPABILITIES = CandidateFilterCapabilities(
    family="opportunity",
    supported_filters=frozenset({"q", "timezone"}),
)

FAMILY_FILTER_CAPABILITIES = {
    "occurrence": OCCURRENCE_FILTER_CAPABILITIES,
    "service": SERVICE_FILTER_CAPABILITIES,
    "opportunity": OPPORTUNITY_FILTER_CAPABILITIES,
}


def active_filter_keys(params) -> frozenset[str]:
    """Return semantic filters that are actually active in Discovery params.

    ``radius_km`` is only a proximity constraint when coordinates are present;
    the HTML form carries a default radius even before geolocation is active.
    ``city`` is a legacy alias for the canonical ``place`` filter.
    """

    params = params or {}
    active: set[str] = set()
    if str(params.get("q") or "").strip():
        active.add("q")
    if str(params.get("place") or params.get("city") or "").strip():
        active.add("place")
    for key in ("when", "period", "vertical", "price", "date", "date_from", "date_to", "timezone"):
        if str(params.get(key) or "").strip():
            active.add(key)
    if str(params.get("lat") or "").strip() or str(params.get("lon") or "").strip():
        active.add("proximity")
    ordering = str(params.get("ordering") or "").strip().lower()
    if ordering:
        active.add("ordering")
    return frozenset(active)


def capabilities_for_family(family: str) -> CandidateFilterCapabilities:
    try:
        return FAMILY_FILTER_CAPABILITIES[family]
    except KeyError as exc:
        raise ValueError(f"Unknown Discovery candidate family: {family}") from exc


def unsupported_filters_for_family(family: str, params) -> tuple[str, ...]:
    return capabilities_for_family(family).unsupported_filters(params)


def family_can_satisfy_filters(family: str, params) -> bool:
    return capabilities_for_family(family).can_satisfy(params)
