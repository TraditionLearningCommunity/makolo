from __future__ import annotations

from dataclasses import dataclass

from .fragments import is_fragment_request


@dataclass(frozen=True)
class SurfaceContext:
    family: str
    owner: str | None
    needs: frozenset[str]
    mode: str

    def needs_capability(self, capability: str) -> bool:
        return capability in self.needs


def surface_context_for_request(request) -> SurfaceContext:
    """Derive shell needs from routing only; this function never hits the DB."""
    match = getattr(request, "resolver_match", None)
    namespace = (match.namespace or "") if match else ""
    url_name = (match.url_name or "") if match else ""
    qualified = f"{namespace}:{url_name}" if namespace else url_name
    authenticated = bool(
        getattr(getattr(request, "user", None), "is_authenticated", False)
    )
    mode = "fragment" if is_fragment_request(request) else "full"

    if namespace == "organizations" and url_name.startswith("console-"):
        family = "space"
        owner = url_name.removeprefix("console-") or "overview"
    elif namespace == "discovery":
        family = "personal"
        owner = "discover"
    elif namespace == "core" and url_name in {
        "participant-home",
        "participant-ongoing",
        "participant-me",
        "makolo-mark",
        "participant-history",
        "participant-connections",
        "participant-journeys",
        "participant-journey-detail",
        "participant-accesses",
        "participant-access-detail",
        "participant-occurrence-live",
    }:
        family = "personal"
        owner = {
            "participant-home": "now",
            "participant-ongoing": "ongoing",
            "participant-me": "me",
            "makolo-mark": "mark",
        }.get(url_name, "detail")
    elif namespace:
        family = namespace
        owner = url_name or None
    else:
        family = "public"
        owner = qualified or None

    needs = set()
    if authenticated:
        needs.update({"account", "profile_activation"})
    if family == "personal":
        needs.add("personal_navigation")
    if family == "space":
        needs.update({"space_navigation", "space_authority"})

    if qualified == "core:participant-home":
        needs.update({"notifications", "conversation_attention"})

    return SurfaceContext(
        family=family,
        owner=owner,
        needs=frozenset(needs),
        mode=mode,
    )
