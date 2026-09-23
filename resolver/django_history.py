from __future__ import annotations

from observer.django_app.models import Observation

from .normalization import endpoint_key
from .ports import FactHistoryComparison
from .django_app.models import ResolutionAssertionRow


def _observed_at(observation_ref):
    return (
        Observation.objects.filter(observation_ref=observation_ref)
        .values_list("observed_at", flat=True)
        .first()
    )


class DjangoResolutionHistory:
    """Read-only comparison against immutable finalized resolution assertions."""

    def compare_fact(self, *, endpoint, predicate, semantic_fingerprint, material):
        key = endpoint_key(endpoint)
        rows = list(
            ResolutionAssertionRow.objects.filter(
                run__lifecycle="finalized",
                subject_key=key,
                predicate=predicate,
                kind__in=["fact", "constraint"],
            )
            .select_related("run")
            .order_by("-run__completed_at", "-id")[:50]
        )
        if not rows:
            return FactHistoryComparison()

        same = [row for row in rows if row.semantic_fingerprint == semantic_fingerprint]
        if same:
            return FactHistoryComparison(
                status="linked",
                related_candidate_refs=tuple(dict.fromkeys(row.candidate_ref for row in same)),
                basis_codes=("historical_same_fact",),
            )

        different = [row for row in rows if row.semantic_fingerprint and row.semantic_fingerprint != semantic_fingerprint]
        if not different:
            return FactHistoryComparison()

        cross_source = [row for row in different if row.run.target_key != material.target_key]
        if cross_source:
            return FactHistoryComparison(
                status="conflict",
                related_candidate_refs=tuple(dict.fromkeys(row.candidate_ref for row in cross_source)),
                basis_codes=("cross_source_conflicting_fact",),
            )

        latest = different[0]
        current_observed_at = _observed_at(material.observation_ref)
        prior_observed_at = _observed_at(latest.run.observation_ref)
        if (
            current_observed_at is not None
            and prior_observed_at is not None
            and current_observed_at > prior_observed_at
        ):
            return FactHistoryComparison(
                status="update",
                related_candidate_refs=(latest.candidate_ref,),
                basis_codes=("same_source_later_observation",),
            )
        return FactHistoryComparison(
            status="conflict",
            related_candidate_refs=tuple(dict.fromkeys(row.candidate_ref for row in different)),
            basis_codes=("same_source_temporal_order_not_newer",),
        )
