from __future__ import annotations

from dataclasses import dataclass

from .intent import ConstraintSource


@dataclass(frozen=True)
class CandidateFilterCapabilities:
    """Read-only contract for filters a Discovery candidate family can prove."""

    family: str
    supported_filters: frozenset[str]

    def unsupported_filters(self, requested_filters) -> tuple[str, ...]:
        return tuple(sorted(set(requested_filters) - self.supported_filters))

    def can_satisfy(self, requested_filters) -> bool:
        return not self.unsupported_filters(requested_filters)


# Candidate family is structural, not vertical: an Occurrence may represent an
# Event, Transport, Service or generic Activity. Capabilities describe what the
# family can prove, not whether a vaguely similar field exists somewhere.
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
    family="service_activity",
    supported_filters=frozenset({"q", "vertical", "timezone"}),
)
OPPORTUNITY_FILTER_CAPABILITIES = CandidateFilterCapabilities(
    family="opportunity",
    supported_filters=frozenset({"q", "timezone"}),
)

FAMILY_FILTER_CAPABILITIES = {
    "occurrence": OCCURRENCE_FILTER_CAPABILITIES,
    "service_activity": SERVICE_FILTER_CAPABILITIES,
    "opportunity": OPPORTUNITY_FILTER_CAPABILITIES,
}


def active_filter_keys(params) -> frozenset[str]:
    """Return semantic filters actually present in one parameter mapping.

    ``radius_km`` is only a proximity constraint when coordinates are present;
    the HTML form carries a default radius before geolocation is active.
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
    if str(params.get("ordering") or "").strip():
        active.add("ordering")
    return frozenset(active)


def requested_filter_keys(*, requested_params=None, constraints=()) -> frozenset[str]:
    """Resolve user/interpreter constraints without treating defaults as intent.

    ``requested_params`` must be the raw user criteria when available, not a
    later search mapping containing technical defaults. Interpreted constraints
    are added from ``DiscoveryIntent.constraints``; DEFAULT constraints never
    exclude a candidate family.
    """

    requested = set(active_filter_keys(requested_params))
    for constraint in constraints or ():
        if getattr(constraint, "source", None) == ConstraintSource.DEFAULT:
            continue
        key = getattr(constraint, "key", "")
        if key == "nearby":
            key = "proximity"
        if key:
            requested.add(key)
    return frozenset(requested)


def capabilities_for_family(family: str) -> CandidateFilterCapabilities:
    try:
        return FAMILY_FILTER_CAPABILITIES[family]
    except KeyError as exc:
        raise ValueError(f"Unknown Discovery candidate family: {family}") from exc


def unsupported_filters_for_family(family: str, requested_filters) -> tuple[str, ...]:
    return capabilities_for_family(family).unsupported_filters(requested_filters)


def family_can_satisfy_filters(family: str, requested_filters) -> bool:
    return capabilities_for_family(family).can_satisfy(requested_filters)
