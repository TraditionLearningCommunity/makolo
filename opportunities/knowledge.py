"""Public, attribution-safe knowledge of Opportunity sources.

An observed or verified source is not a certification that every fact in the
current published revision is still true. This read model never initiates
remote checks or exposes internal source notes, reviewers or fingerprints.
"""
from __future__ import annotations

from .models import OpportunitySource, OpportunitySourceStatus
from .selectors import published_opportunities


MAX_PUBLIC_SOURCE_OBSERVATIONS = 8


def public_source_knowledge(opportunity_id) -> dict | None:
    """Return bounded public evidence about a published Opportunity's sources.

    Source checks are observations of sources, not freshness guarantees for
    deadlines, terms, eligibility or other owner facts. Withdrawn, merged and
    draft Opportunities have no public knowledge projection.
    """
    opportunity = (
        published_opportunities()
        .filter(pk=opportunity_id)
        .first()
    )
    if opportunity is None:
        return None

    source_rows = list(
        OpportunitySource.objects.filter(
            opportunity=opportunity,
            status=OpportunitySourceStatus.ACTIVE,
        )
        .order_by("-is_primary", "id")
        .values("id", "source_type", "is_primary", "last_checked_at", "verified_at")
        [: MAX_PUBLIC_SOURCE_OBSERVATIONS + 1]
    )
    truncated = len(source_rows) > MAX_PUBLIC_SOURCE_OBSERVATIONS
    observations = [
        {
            "source": {"kind": "opportunity_source", "id": str(row["id"])},
            "source_type": row["source_type"],
            "primary": row["is_primary"],
            "last_checked_at": (
                row["last_checked_at"].isoformat()
                if row["last_checked_at"] is not None else None
            ),
            "verified_at": (
                row["verified_at"].isoformat()
                if row["verified_at"] is not None else None
            ),
        }
        for row in source_rows[:MAX_PUBLIC_SOURCE_OBSERVATIONS]
    ]
    revision = opportunity.current_revision
    return {
        "opportunity": {"kind": "opportunity", "id": str(opportunity.pk)},
        "revision": {"kind": "opportunity_revision", "id": str(revision.pk)},
        "revision_published_at": (
            revision.published_at.isoformat()
            if revision.published_at is not None else None
        ),
        "source_observations": observations,
        "source_observations_truncated": truncated,
        # Source verification/checks are not a fact-by-fact freshness proof.
        "fact_freshness": "not_asserted",
    }
