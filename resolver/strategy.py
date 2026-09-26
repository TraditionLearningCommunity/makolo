from __future__ import annotations

from dataclasses import replace
import re

from interpreter.contracts import (
    CandidateConstraint,
    CandidateEntity,
    CandidateFact,
    CandidateRelation,
    InterpretationOutcome,
    candidate_storage_payload,
)

from .contracts import (
    AssertionKind,
    EndpointKind,
    ResolvedMaterial,
    ResolutionAssertion,
    ResolutionEndpoint,
    ResolutionMethod,
    ResolutionOutcome,
    ResolutionStatus,
    ResolutionStrength,
    assign_assertion_ref,
)
from .errors import ResolverContractError
from .identifiers import make_provisional_ref, make_resolution_ref, strategy_fingerprint
from .normalization import endpoint_key, normalize_text, semantic_fingerprint
from .ports import FactHistoryComparison

STRATEGY_KEY = "deterministic-first"
STRATEGY_VERSION = "1.1"
STRATEGY_COMPONENTS = {
    "contracts": "1",
    "family_routing": "1",
    "canonical_lookup": "1",
    "history_comparison": "1",
    "conflicts": "2",
}
STRATEGY_FINGERPRINT = strategy_fingerprint(STRATEGY_COMPONENTS)

# Only predicates with a clear single-value semantic may conflict merely because
# two different values appear in the same interpreted material. Everything else
# is additive by default: contacts, links, references and requirements can be
# legitimately multivalued.
_SINGLE_VALUED_FACT_PREDICATES = frozenset({
    "publication_date",
    "start_date",
    "end_date",
    "deadline",
    "duration",
    "form_available",
})


def _locally_exclusive_fact(candidate) -> bool:
    return isinstance(candidate, CandidateFact) and candidate.predicate in _SINGLE_VALUED_FACT_PREDICATES


def _facts_by_subject(material):
    result = {}
    for candidate in material.candidates:
        if isinstance(candidate, (CandidateFact, CandidateConstraint)):
            result.setdefault(candidate.subject_ref, []).append(candidate)
    return result


def _entity_families(entity, facts):
    hints = {item.lower() for item in entity.type_hints}
    if hints & {"organization", "corporation", "educationalorganization", "ngo", "governmentorganization"}:
        return ("organization",)
    if hints & {"place", "postaladdress", "city", "country", "geography"}:
        return ("geography_place",)
    if hints & {"jobposting", "employment", "funding_program", "scholarship", "grant", "internship"}:
        return ("opportunity",)
    if hints & {"training", "course", "event", "assessment", "exam"}:
        dated = any(getattr(item, "predicate", "") in {"start_date", "mentioned_date"} for item in facts)
        return ("occurrence", "activity") if dated else ("activity",)
    if hints & {"requirement_subject", "experience", "condition_subject", "funded_resource"}:
        return ("requirement_concept",)
    return ("reality",)


def _looks_like_ambiguous_alias(label):
    compact = re.sub(r"[^A-Za-z0-9]", "", label or "")
    return 2 <= len(compact) <= 10 and compact.isupper()


def _choose_lookup(lookup):
    alternatives = tuple(lookup.alternatives)
    exact = tuple(item for item in alternatives if item.strength is ResolutionStrength.EXACT)
    strong = tuple(item for item in alternatives if item.strength is ResolutionStrength.STRONG)
    if len(exact) == 1:
        return ResolutionStatus.MATCHED, exact[0], alternatives
    if len(exact) > 1:
        return ResolutionStatus.AMBIGUOUS, None, exact
    if len(strong) == 1:
        return ResolutionStatus.MATCHED, strong[0], alternatives
    if len(strong) > 1:
        return ResolutionStatus.AMBIGUOUS, None, strong
    if alternatives:
        return ResolutionStatus.AMBIGUOUS, None, alternatives
    return ResolutionStatus.NEW_CANDIDATE, None, ()


def _endpoint(assertion):
    if assertion.status is ResolutionStatus.MATCHED:
        return ResolutionEndpoint(
            EndpointKind.CANONICAL,
            f"{assertion.canonical_ref.domain}:{assertion.canonical_ref.object_ref}",
            assertion.canonical_ref,
        )
    if assertion.status is ResolutionStatus.NEW_CANDIDATE:
        return ResolutionEndpoint(EndpointKind.PROVISIONAL, assertion.provisional_ref)
    return ResolutionEndpoint(EndpointKind.CANDIDATE, assertion.candidate_ref)


def _fact_like_payload(candidate):
    payload = candidate_storage_payload(candidate)
    return payload, semantic_fingerprint(
        {
            "kind": payload.get("kind"),
            "predicate": payload.get("predicate"),
            "value": payload.get("value"),
            "second_value": payload.get("second_value"),
            "operator": payload.get("operator"),
            "modality": payload.get("modality"),
            "condition_ref": payload.get("condition_ref"),
            "logic_group": payload.get("logic_group"),
            "logic_operator": payload.get("logic_operator"),
        }
    )


class DeterministicResolver:
    strategy_key = STRATEGY_KEY
    strategy_version = STRATEGY_VERSION
    strategy_fingerprint = STRATEGY_FINGERPRINT

    def resolve(self, material, catalog, history, *, started_at, clock):
        if material.outcome not in {InterpretationOutcome.INTERPRETED, InterpretationOutcome.PARTIAL}:
            raise ResolverContractError("Resolver accepts interpreted or partial material only")

        resolution_ref = make_resolution_ref(
            interpretation_ref=material.interpretation_ref,
            strategy_fingerprint=self.strategy_fingerprint,
        )
        facts_by_subject = _facts_by_subject(material)
        entity_assertions = {}
        assertions = []
        warnings = list(material.warning_codes)

        for entity in (item for item in material.candidates if isinstance(item, CandidateEntity)):
            families = _entity_families(entity, facts_by_subject.get(entity.candidate_ref, ()))
            context = {
                "families": families,
                "facts": tuple(facts_by_subject.get(entity.candidate_ref, ())),
                "all_candidates": material.candidates,
            }
            lookup = catalog.lookup_entity(material, entity, context)
            status, selected, alternatives = _choose_lookup(lookup)
            provisional = None
            canonical = None
            method = None
            strength = None
            basis = tuple(lookup.basis_codes)
            if (
                status is ResolutionStatus.NEW_CANDIDATE
                and families[0] in {"organization", "geography_place", "reality"}
                and _looks_like_ambiguous_alias(entity.label)
            ):
                status = ResolutionStatus.UNRESOLVED
                basis = tuple(dict.fromkeys((*basis, "short_alias_without_evidence")))
            if selected is not None:
                canonical = selected.canonical_ref
                method = selected.method
                strength = selected.strength
                basis = tuple(dict.fromkeys((*basis, *selected.basis_codes)))
            elif status is ResolutionStatus.NEW_CANDIDATE:
                identity_key = lookup.provisional_identity_key or (
                    f"{material.target_key}|{families[0]}|{normalize_text(entity.label)}"
                )
                provisional = make_provisional_ref(family=families[0], identity_key=identity_key)
                method = ResolutionMethod.DETERMINISTIC
                strength = ResolutionStrength.POSSIBLE
                basis = tuple(dict.fromkeys((*basis, "no_safe_canonical_match")))
            assertion = ResolutionAssertion(
                assertion_ref="pending",
                candidate_ref=entity.candidate_ref,
                kind=AssertionKind.ENTITY,
                status=status,
                canonical_ref=canonical,
                provisional_ref=provisional,
                method=method,
                strength=strength,
                basis_codes=basis,
                alternatives=alternatives,
                candidate_payload=candidate_storage_payload(entity),
            )
            assertion = assign_assertion_ref(resolution_ref=resolution_ref, assertion=assertion)
            entity_assertions[entity.candidate_ref] = assertion
            assertions.append(assertion)

        local_fact_groups = {}
        pending_conflicts = []
        pending_history_conflicts = []
        for candidate in material.candidates:
            if not isinstance(candidate, (CandidateFact, CandidateConstraint)):
                continue
            subject_assertion = entity_assertions.get(candidate.subject_ref)
            subject = _endpoint(subject_assertion) if subject_assertion else (
                ResolutionEndpoint(EndpointKind.CANDIDATE, candidate.subject_ref)
                if candidate.subject_ref else None
            )
            payload, fingerprint = _fact_like_payload(candidate)
            kind = AssertionKind.FACT if isinstance(candidate, CandidateFact) else AssertionKind.CONSTRAINT
            status = ResolutionStatus.LINKED if subject and subject.kind is not EndpointKind.CANDIDATE else ResolutionStatus.PARTIAL
            basis = ["subject_resolved"] if status is ResolutionStatus.LINKED else ["subject_not_resolved"]
            related = ()
            if subject is not None and status is ResolutionStatus.LINKED:
                comparison = history.compare_fact(
                    endpoint=subject,
                    predicate=candidate.predicate,
                    semantic_fingerprint=fingerprint,
                    material=material,
                )
                if comparison.status in {"linked", "update", "conflict"}:
                    status = ResolutionStatus(comparison.status)
                    basis.extend(comparison.basis_codes)
                    related = comparison.related_candidate_refs
                    if comparison.status == "conflict":
                        pending_history_conflicts.append((candidate, subject, comparison.related_candidate_refs, comparison.basis_codes))
            group_key = (endpoint_key(subject), candidate.predicate, kind.value)
            previous = local_fact_groups.setdefault(group_key, [])
            if (
                _locally_exclusive_fact(candidate)
                and any(other_fingerprint != fingerprint for _, other_fingerprint in previous)
            ):
                status = ResolutionStatus.CONFLICT
                basis.append("same_material_conflicting_values")
                pending_conflicts.append((candidate, subject, tuple(ref for ref, _ in previous)))
            previous.append((candidate.candidate_ref, fingerprint))
            assertion = ResolutionAssertion(
                assertion_ref="pending",
                candidate_ref=candidate.candidate_ref,
                kind=kind,
                status=status,
                subject=subject,
                predicate=candidate.predicate,
                basis_codes=tuple(dict.fromkeys(basis)),
                related_candidate_refs=related,
                candidate_payload=payload,
                semantic_fingerprint=fingerprint,
            )
            assertions.append(assign_assertion_ref(resolution_ref=resolution_ref, assertion=assertion))

        for candidate in (item for item in material.candidates if isinstance(item, CandidateRelation)):
            subject_assertion = entity_assertions.get(candidate.subject_ref)
            object_assertion = entity_assertions.get(candidate.object_ref)
            subject = _endpoint(subject_assertion) if subject_assertion else ResolutionEndpoint(EndpointKind.CANDIDATE, candidate.subject_ref)
            obj = _endpoint(object_assertion) if object_assertion else ResolutionEndpoint(EndpointKind.CANDIDATE, candidate.object_ref)
            fully_linked = subject.kind is not EndpointKind.CANDIDATE and obj.kind is not EndpointKind.CANDIDATE
            assertion = ResolutionAssertion(
                assertion_ref="pending",
                candidate_ref=candidate.candidate_ref,
                kind=AssertionKind.RELATION,
                status=ResolutionStatus.LINKED if fully_linked else ResolutionStatus.PARTIAL,
                subject=subject,
                object=obj,
                predicate=candidate.predicate,
                basis_codes=("endpoints_resolved",) if fully_linked else ("partial_endpoint_resolution",),
                candidate_payload=candidate_storage_payload(candidate),
            )
            assertions.append(assign_assertion_ref(resolution_ref=resolution_ref, assertion=assertion))

        for candidate, subject, prior_refs, history_basis in pending_history_conflicts:
            payload = {
                "predicate": candidate.predicate,
                "subject": subject.to_payload() if subject else None,
                "candidate_refs": [*prior_refs, candidate.candidate_ref],
                "reason": "historical_conflicting_value",
            }
            conflict = ResolutionAssertion(
                assertion_ref="pending",
                candidate_ref=candidate.candidate_ref,
                kind=AssertionKind.CONFLICT,
                status=ResolutionStatus.CONFLICT,
                subject=subject,
                predicate=candidate.predicate,
                basis_codes=tuple(dict.fromkeys((*history_basis, "historical_conflicting_value"))),
                related_candidate_refs=prior_refs,
                candidate_payload=payload,
                semantic_fingerprint=semantic_fingerprint(payload),
            )
            assertions.append(assign_assertion_ref(resolution_ref=resolution_ref, assertion=conflict))

        for candidate, subject, prior_refs in pending_conflicts:
            payload = {
                "predicate": candidate.predicate,
                "subject": subject.to_payload() if subject else None,
                "candidate_refs": [*prior_refs, candidate.candidate_ref],
                "reason": "same_material_conflicting_values",
            }
            conflict = ResolutionAssertion(
                assertion_ref="pending",
                candidate_ref=candidate.candidate_ref,
                kind=AssertionKind.CONFLICT,
                status=ResolutionStatus.CONFLICT,
                subject=subject,
                predicate=candidate.predicate,
                basis_codes=("same_material_conflicting_values",),
                related_candidate_refs=prior_refs,
                candidate_payload=payload,
                semantic_fingerprint=semantic_fingerprint(payload),
            )
            assertions.append(assign_assertion_ref(resolution_ref=resolution_ref, assertion=conflict))

        statuses = {item.status for item in assertions}
        if ResolutionStatus.CONFLICT in statuses:
            outcome = ResolutionOutcome.CONFLICT
        elif ResolutionStatus.AMBIGUOUS in statuses:
            outcome = ResolutionOutcome.AMBIGUOUS
        elif not assertions or statuses <= {ResolutionStatus.UNRESOLVED, ResolutionStatus.PARTIAL}:
            outcome = ResolutionOutcome.UNRESOLVED
        elif statuses & {ResolutionStatus.UNRESOLVED, ResolutionStatus.PARTIAL}:
            outcome = ResolutionOutcome.PARTIAL
        else:
            outcome = ResolutionOutcome.RESOLVED

        if material.outcome is InterpretationOutcome.PARTIAL:
            warnings.append("upstream_partial")
            if outcome is ResolutionOutcome.RESOLVED:
                outcome = ResolutionOutcome.PARTIAL

        output = ResolvedMaterial(
            resolution_ref=resolution_ref,
            interpretation_ref=material.interpretation_ref,
            material_key=material.material_key,
            observation_ref=material.observation_ref,
            target_key=material.target_key,
            strategy_key=self.strategy_key,
            strategy_version=self.strategy_version,
            strategy_fingerprint=self.strategy_fingerprint,
            started_at=started_at,
            completed_at=clock(),
            outcome=outcome,
            assertions=tuple(assertions),
            warning_codes=tuple(dict.fromkeys(warnings)),
        )
        stats = {
            "assertion_count": len(assertions),
            "entity_count": len(output.entity_resolutions),
            "fact_count": len(output.fact_resolutions),
            "relation_count": len(output.relation_resolutions),
            "constraint_count": len(output.constraint_resolutions),
            "conflict_count": len(output.conflicts),
            "matched_count": sum(item.status is ResolutionStatus.MATCHED for item in assertions),
            "new_candidate_count": sum(item.status is ResolutionStatus.NEW_CANDIDATE for item in assertions),
            "ambiguous_count": sum(item.status is ResolutionStatus.AMBIGUOUS for item in assertions),
            "heuristic_decisions": sum(item.method is ResolutionMethod.HEURISTIC for item in assertions),
            "model_calls": 0,
            "network_calls": 0,
        }
        return output, stats
