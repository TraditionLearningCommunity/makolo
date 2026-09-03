from __future__ import annotations

from .intent import DiscoveryIntent, resolve_discovery_intent
from .search import DiscoverySearchResult, search_occurrences


def search_discovery_intent(intent: DiscoveryIntent, *, profile=None, now=None) -> DiscoverySearchResult:
    return search_occurrences(intent.to_search_params(), profile=profile, now=now)


def resolve_and_search(params, *, profile=None, now=None):
    intent = resolve_discovery_intent(params)
    result = search_discovery_intent(intent, profile=profile, now=now)
    return intent, result
