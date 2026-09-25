from __future__ import annotations

"""Small benchmark helpers for Actor 3 closure.

The benchmark compares semantic payloads, not raw candidate counts.  More
candidates are not treated as an improvement by themselves.
"""

from dataclasses import dataclass
from time import monotonic

from .contracts import CandidateEntity, CandidateFact, CandidateRelation, CandidateConstraint


@dataclass(frozen=True, slots=True)
class BenchmarkExpectation:
    entity_labels: frozenset[str] = frozenset()
    predicates: frozenset[str] = frozenset()
    allowed_predicates: frozenset[str] | None = None
    forbidden_entity_hints: frozenset[str] = frozenset()


def _labels(material):
    return {
        item.label
        for item in material.candidates
        if isinstance(item, CandidateEntity)
    }


def _predicates(material):
    return {
        item.predicate
        for item in material.candidates
        if isinstance(item, (CandidateFact, CandidateRelation, CandidateConstraint))
    }


def benchmark_interpretation(strategy, material, artifact_reader, expectation, *, started_at, clock):
    before = monotonic()
    output, stats = strategy.interpret(
        material,
        artifact_reader,
        started_at=started_at,
        clock=clock,
    )
    elapsed_ms = max(int((monotonic() - before) * 1000), 0)

    labels = _labels(output)
    predicates = _predicates(output)
    entity_hints = {
        hint
        for item in output.candidates
        if isinstance(item, CandidateEntity)
        for hint in item.type_hints
    }
    evidence_count = sum(len(item.evidence) for item in output.candidates)
    missing_evidence = sum(not item.evidence for item in output.candidates)

    semantic_keys = []
    for item in output.candidates:
        semantic_keys.append((item.kind.value, repr(item.semantic_payload())))
    duplicate_semantics = len(semantic_keys) - len(set(semantic_keys))

    value_kinds = {}
    fact_values = []
    for item in output.candidates:
        value = getattr(item, "value", None)
        if value is not None:
            value_kinds[value.kind.value] = value_kinds.get(value.kind.value, 0) + 1
            if isinstance(item, CandidateFact):
                fact_values.append((item.subject_ref, item.predicate, repr(value.to_payload())))
    contradictory_groups = {}
    for subject_ref, predicate, payload in fact_values:
        contradictory_groups.setdefault((subject_ref, predicate), set()).add(payload)
    contradiction_count = sum(len(values) > 1 for values in contradictory_groups.values())
    unexpected_predicates = []
    if expectation.allowed_predicates is not None:
        unexpected_predicates = sorted(predicates.difference(expectation.allowed_predicates))

    report = {
        "expected_entities": len(expectation.entity_labels),
        "found_expected_entities": len(expectation.entity_labels.intersection(labels)),
        "false_negative_entities": sorted(expectation.entity_labels.difference(labels)),
        "expected_predicates": len(expectation.predicates),
        "found_expected_predicates": len(expectation.predicates.intersection(predicates)),
        "false_negative_predicates": sorted(expectation.predicates.difference(predicates)),
        "forbidden_hints_present": sorted(expectation.forbidden_entity_hints.intersection(entity_hints)),
        "unexpected_predicates": unexpected_predicates,
        "candidate_count": len(output.candidates),
        "evidence_count": evidence_count,
        "missing_evidence_count": missing_evidence,
        "duplicate_semantic_count": duplicate_semantics,
        "contradiction_group_count": contradiction_count,
        "value_kind_counts": value_kinds,
        "elapsed_ms": elapsed_ms,
        "bytes_read": int(stats.get("bytes_read", 0)),
        "intelligence_calls": int(stats.get("intelligence_calls", stats.get("llm_calls", 0))),
        "intelligence_candidates_accepted": int(stats.get("intelligence_candidates_accepted", 0)),
        "intelligence_candidates_rejected": int(stats.get("intelligence_candidates_rejected", 0)),
        "provider_cost": None,
    }
    return output, report
