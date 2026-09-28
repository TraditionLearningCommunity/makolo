from __future__ import annotations

from opportunities.models import (
    OpportunityPublicationStatus,
    OpportunitySource,
)
from organizations.models import Organization
from prospector.canonicalization import canonicalize_web_url

from .discovery import (
    DiscoveryKnowledgeState,
    DiscoveryKnownRef,
    DiscoveryLookup,
)


MAX_SOURCE_SCAN = 100


def _canonical(value: str) -> str | None:
    try:
        return canonicalize_web_url(value)
    except Exception:
        return None


class DjangoDiscoveryKnowledgeCatalog:
    """Read-only exact source lookup for the first generic Discovery vertical.

    This adapter deliberately proves only positive exact knowledge. When a URL
    is absent from the catalogs currently covered here, it returns UNRESOLVED,
    not NOT_KNOWN: absence from these bounded tables is not proof that Makolo
    knows nothing about the underlying reality.
    """

    def lookup(self, *, result, candidate, sources):
        refs = {}

        for source in sources:
            canonical = _canonical(source.locator)
            if canonical is None:
                continue

            opportunity_rows = (
                OpportunitySource.objects.select_related("opportunity")
                .exclude(
                    opportunity__publication_status=OpportunityPublicationStatus.MERGED
                )
                .order_by("id")[:MAX_SOURCE_SCAN]
            )
            for row in opportunity_rows:
                if _canonical(row.url) != canonical:
                    continue
                ref = DiscoveryKnownRef(
                    domain="opportunity",
                    object_ref=str(row.opportunity_id),
                )
                refs[(ref.domain, ref.object_ref)] = ref

            organization_rows = (
                Organization.objects.exclude(website="")
                .order_by("id")[:MAX_SOURCE_SCAN]
            )
            for row in organization_rows:
                if _canonical(row.website) != canonical:
                    continue
                ref = DiscoveryKnownRef(
                    domain="organization",
                    object_ref=str(row.pk),
                )
                refs[(ref.domain, ref.object_ref)] = ref

        known_refs = tuple(refs.values())
        if len(known_refs) == 1:
            return DiscoveryLookup(
                state=DiscoveryKnowledgeState.KNOWN,
                known_refs=known_refs,
                basis_codes=("exact_known_source_url",),
            )
        if len(known_refs) > 1:
            return DiscoveryLookup(
                state=DiscoveryKnowledgeState.AMBIGUOUS,
                known_refs=known_refs,
                basis_codes=("exact_source_url_multiple_realities",),
            )
        return DiscoveryLookup(
            state=DiscoveryKnowledgeState.UNRESOLVED,
            basis_codes=("no_exact_known_source",),
        )
