from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol, runtime_checkable

from research_missions import (
    ResearchFamily,
    ResearchMission,
    ResearchMissionCandidate,
    ResearchOrigin,
    ResearchOriginKind,
)

from .contracts import WebResearchContractError
from .discovery import DiscoveryOutput, DiscoveryRecord


DEEPEN_OUTPUT_CONTRACT_VERSION = 1


class FamilyCoverageState(str, Enum):
    """Coverage of one research family in the material already acquired.

    MISSING means missing from current material, never absent from reality.
    """

    PRESENT = "present"
    PARTIAL = "partial"
    MISSING = "missing"
    CONFLICTING = "conflicting"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class FamilyCoverage:
    family: ResearchFamily
    state: FamilyCoverageState
    basis_codes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "family", ResearchFamily(self.family))
        object.__setattr__(
            self,
            "state",
            FamilyCoverageState(self.state),
        )
        normalized = []
        for value in tuple(self.basis_codes or ()):
            value = str(value).strip().lower()
            if (
                not value
                or not value[0].isalpha()
                or any(
                    char not in "abcdefghijklmnopqrstuvwxyz0123456789_.:-"
                    for char in value
                )
            ):
                raise WebResearchContractError(
                    "coverage basis_codes must contain stable technical codes"
                )
            if value not in normalized:
                normalized.append(value)
        object.__setattr__(self, "basis_codes", tuple(normalized))

    def to_payload(self):
        return {
            "family": self.family.value,
            "state": self.state.value,
            "basis_codes": list(self.basis_codes),
        }


@dataclass(frozen=True, slots=True)
class DeepenFamilySpec:
    """One reusable family-level question in a generic deepen specification."""

    family: ResearchFamily
    questions: tuple[str, ...]
    unknowns: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "family", ResearchFamily(self.family))
        questions = tuple(
            dict.fromkeys(
                " ".join(str(value).split())
                for value in tuple(self.questions or ())
                if str(value).strip()
            )
        )
        if not questions:
            raise WebResearchContractError(
                "deepen family spec requires at least one question"
            )
        object.__setattr__(self, "questions", questions)
        object.__setattr__(
            self,
            "unknowns",
            tuple(
                dict.fromkeys(
                    " ".join(str(value).split())
                    for value in tuple(self.unknowns or ())
                    if str(value).strip()
                )
            ),
        )

    def to_payload(self):
        return {
            "family": self.family.value,
            "questions": list(self.questions),
            "unknowns": list(self.unknowns),
        }


@dataclass(frozen=True, slots=True)
class DeepenSpecification:
    """Reusable skeleton selecting what a mission wants to deepen.

    It is deliberately not a persistent model. A scholarship, transport,
    employment or other vertical may instantiate this generic specification
    with the families/questions it needs.
    """

    family_specs: tuple[DeepenFamilySpec, ...]
    include_partial: bool = True
    include_conflicting: bool = True

    def __post_init__(self) -> None:
        specs = tuple(self.family_specs)
        if not specs or any(
            not isinstance(item, DeepenFamilySpec) for item in specs
        ):
            raise WebResearchContractError(
                "deepen specification requires DeepenFamilySpec values"
            )
        families = [item.family for item in specs]
        if len(families) != len(set(families)):
            raise WebResearchContractError(
                "deepen specification families must be unique"
            )
        object.__setattr__(self, "family_specs", specs)

    def to_payload(self):
        return {
            "family_specs": [item.to_payload() for item in self.family_specs],
            "include_partial": self.include_partial,
            "include_conflicting": self.include_conflicting,
        }


@runtime_checkable
class FamilyCoveragePort(Protocol):
    """Read-only assessment of what current candidate material already covers."""

    def assess(
        self,
        *,
        parent_mission: ResearchMission,
        discovery: DiscoveryOutput,
        record: DiscoveryRecord,
        specification: DeepenSpecification,
    ) -> tuple[FamilyCoverage, ...]:
        ...


class MinimalDiscoveryCoverage:
    """Safe Phase-4 baseline based only on standard Discovery material.

    Discovery itself establishes that a possibility candidate and at least one
    reference were observed. It does not pretend that actor, requirements,
    qualification, spatiotemporal, procedure or economic details were acquired.
    """

    def assess(
        self,
        *,
        parent_mission: ResearchMission,
        discovery: DiscoveryOutput,
        record: DiscoveryRecord,
        specification: DeepenSpecification,
    ) -> tuple[FamilyCoverage, ...]:
        present = {
            ResearchFamily.POSSIBILITY,
            ResearchFamily.REFERENCE,
        }
        coverage = []
        for spec in specification.family_specs:
            if spec.family in present:
                coverage.append(
                    FamilyCoverage(
                        family=spec.family,
                        state=FamilyCoverageState.PRESENT,
                        basis_codes=(
                            "discovery_candidate_observed"
                            if spec.family is ResearchFamily.POSSIBILITY
                            else "discovery_source_present",
                        ),
                    )
                )
            else:
                coverage.append(
                    FamilyCoverage(
                        family=spec.family,
                        state=FamilyCoverageState.MISSING,
                        basis_codes=("not_present_in_discovery_material",),
                    )
                )
        return tuple(coverage)


@dataclass(frozen=True, slots=True)
class DeepenMissionSuggestion:
    candidate_ref: str
    family: ResearchFamily
    mission_candidate: ResearchMissionCandidate

    def __post_init__(self) -> None:
        if not isinstance(self.mission_candidate, ResearchMissionCandidate):
            raise WebResearchContractError(
                "deepen suggestion requires ResearchMissionCandidate"
            )
        family = ResearchFamily(self.family)
        if family is not self.mission_candidate.primary_family:
            raise WebResearchContractError(
                "suggestion family must match mission candidate family"
            )
        object.__setattr__(self, "family", family)
        if not isinstance(self.candidate_ref, str) or not self.candidate_ref.strip():
            raise WebResearchContractError(
                "deepen suggestion candidate_ref must not be empty"
            )

    @property
    def mission_ref(self) -> str:
        return self.mission_candidate.mission_ref

    def to_payload(self):
        mission = self.mission_candidate.to_mission()
        return {
            "candidate_ref": self.candidate_ref,
            "family": self.family.value,
            "mission_ref": mission.mission_ref,
            "mission": dict(mission.to_provenance_payload()),
        }


@dataclass(frozen=True, slots=True)
class DeepenTarget:
    candidate_ref: str
    knowledge_state: str
    coverage: tuple[FamilyCoverage, ...]
    suggested_mission_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        coverage = tuple(self.coverage)
        if any(not isinstance(item, FamilyCoverage) for item in coverage):
            raise WebResearchContractError(
                "deepen target coverage must contain FamilyCoverage"
            )
        families = [item.family for item in coverage]
        if len(families) != len(set(families)):
            raise WebResearchContractError(
                "deepen target coverage families must be unique"
            )
        object.__setattr__(self, "coverage", coverage)
        object.__setattr__(
            self,
            "suggested_mission_refs",
            tuple(dict.fromkeys(self.suggested_mission_refs)),
        )

    def to_payload(self):
        return {
            "candidate_ref": self.candidate_ref,
            "knowledge_state": self.knowledge_state,
            "coverage": [item.to_payload() for item in self.coverage],
            "suggested_mission_refs": list(self.suggested_mission_refs),
        }


@dataclass(frozen=True, slots=True)
class DeepenOutput:
    """Standard provider-neutral output of Phase 4 planning."""

    parent_mission_ref: str
    discovery_request_ref: str
    generated_at: datetime
    targets: tuple[DeepenTarget, ...] = ()
    suggestions: tuple[DeepenMissionSuggestion, ...] = ()
    contract_version: int = DEEPEN_OUTPUT_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if not self.parent_mission_ref or not self.discovery_request_ref:
            raise WebResearchContractError(
                "deepen output requires parent mission and discovery refs"
            )
        if (
            not isinstance(self.generated_at, datetime)
            or self.generated_at.tzinfo is None
            or self.generated_at.utcoffset() is None
        ):
            raise WebResearchContractError(
                "deepen output generated_at must be timezone-aware"
            )
        object.__setattr__(
            self,
            "generated_at",
            self.generated_at.astimezone(timezone.utc),
        )
        targets = tuple(self.targets)
        suggestions = tuple(self.suggestions)
        if any(not isinstance(item, DeepenTarget) for item in targets):
            raise WebResearchContractError(
                "deepen output targets must contain DeepenTarget"
            )
        if any(
            not isinstance(item, DeepenMissionSuggestion)
            for item in suggestions
        ):
            raise WebResearchContractError(
                "deepen output suggestions must contain DeepenMissionSuggestion"
            )
        object.__setattr__(self, "targets", targets)
        object.__setattr__(self, "suggestions", suggestions)
        if self.contract_version != DEEPEN_OUTPUT_CONTRACT_VERSION:
            raise WebResearchContractError(
                "unsupported deepen output contract version"
            )

    @property
    def suggestion_count(self) -> int:
        return len(self.suggestions)

    def to_payload(self):
        return {
            "contract_version": self.contract_version,
            "parent_mission_ref": self.parent_mission_ref,
            "discovery_request_ref": self.discovery_request_ref,
            "generated_at": self.generated_at.isoformat(),
            "target_count": len(self.targets),
            "suggestion_count": self.suggestion_count,
            "targets": [item.to_payload() for item in self.targets],
            "suggestions": [item.to_payload() for item in self.suggestions],
        }


class DeepenPlanner:
    """Plan targeted follow-up missions without scheduling or executing them."""

    def __init__(self, coverage: FamilyCoveragePort):
        self.coverage = coverage

    def plan(
        self,
        *,
        parent_mission: ResearchMission,
        discovery: DiscoveryOutput,
        specification: DeepenSpecification,
        generated_at: datetime,
    ) -> DeepenOutput:
        if not isinstance(parent_mission, ResearchMission):
            raise WebResearchContractError(
                "parent_mission must be a ResearchMission"
            )
        if not isinstance(discovery, DiscoveryOutput):
            raise WebResearchContractError(
                "discovery must be a DiscoveryOutput"
            )
        if discovery.mission_ref != parent_mission.mission_ref:
            raise WebResearchContractError(
                "discovery mission does not match parent_mission"
            )
        if not isinstance(specification, DeepenSpecification):
            raise WebResearchContractError(
                "specification must be a DeepenSpecification"
            )

        specs = {item.family: item for item in specification.family_specs}
        targets = []
        suggestions = []

        for record in discovery.records:
            coverage = self.coverage.assess(
                parent_mission=parent_mission,
                discovery=discovery,
                record=record,
                specification=specification,
            )
            if not isinstance(coverage, tuple):
                coverage = tuple(coverage)
            if {item.family for item in coverage} != set(specs):
                raise WebResearchContractError(
                    "coverage must return exactly the specified families"
                )

            record_suggestions = []
            for item in coverage:
                should_suggest = (
                    item.state is FamilyCoverageState.MISSING
                    or (
                        item.state is FamilyCoverageState.PARTIAL
                        and specification.include_partial
                    )
                    or (
                        item.state is FamilyCoverageState.CONFLICTING
                        and specification.include_conflicting
                    )
                )
                if not should_suggest:
                    continue

                family_spec = specs[item.family]
                origin = ResearchOrigin(
                    kind=ResearchOriginKind.PREVIOUS_PROCESSING,
                    source_ref=record.candidate_ref,
                    context={
                        "parent_mission_ref": parent_mission.mission_ref,
                        "discovery_request_ref": discovery.request_ref,
                        "family": item.family.value,
                    },
                )
                candidate = ResearchMissionCandidate(
                    primary_family=item.family,
                    subject=record.label,
                    questions=family_spec.questions,
                    known_context={
                        "candidate_ref": record.candidate_ref,
                        "label": record.label,
                        "source_refs": list(record.source_refs),
                        "type_hints": list(record.type_hints),
                        "summary": record.summary,
                        "knowledge_state": record.knowledge_state.value,
                    },
                    unknowns=family_spec.unknowns,
                    origin=origin,
                    reason=(
                        "Approfondir une dimension absente, partielle ou "
                        "contradictoire du matériau de découverte."
                    ),
                    priority=parent_mission.priority,
                    scope=dict(parent_mission.scope),
                    limits=dict(parent_mission.limits),
                )
                suggestion = DeepenMissionSuggestion(
                    candidate_ref=record.candidate_ref,
                    family=item.family,
                    mission_candidate=candidate,
                )
                suggestions.append(suggestion)
                record_suggestions.append(suggestion.mission_ref)

            targets.append(
                DeepenTarget(
                    candidate_ref=record.candidate_ref,
                    knowledge_state=record.knowledge_state.value,
                    coverage=coverage,
                    suggested_mission_refs=tuple(record_suggestions),
                )
            )

        return DeepenOutput(
            parent_mission_ref=parent_mission.mission_ref,
            discovery_request_ref=discovery.request_ref,
            generated_at=generated_at,
            targets=tuple(targets),
            suggestions=tuple(suggestions),
        )


STANDARD_ACTION_RESEARCH_SPECIFICATION = DeepenSpecification(
    family_specs=(
        DeepenFamilySpec(
            ResearchFamily.POSSIBILITY,
            ("Qu'est-ce que cette possibilité est exactement et quel est son statut observable ?",),
        ),
        DeepenFamilySpec(
            ResearchFamily.ACTOR,
            ("Quels acteurs identifiables portent, proposent, délivrent ou encadrent cette possibilité ?",),
        ),
        DeepenFamilySpec(
            ResearchFamily.REQUIREMENT,
            ("Quelles conditions observables doivent être satisfaites pour accéder à cette possibilité ?",),
        ),
        DeepenFamilySpec(
            ResearchFamily.QUALIFICATION,
            ("Quelles qualifications, preuves ou attestations observables sont demandées ou reconnues ?",),
        ),
        DeepenFamilySpec(
            ResearchFamily.SPATIOTEMPORAL,
            ("Où et quand cette possibilité existe-t-elle, et quelles bornes temporelles sont observables ?",),
        ),
        DeepenFamilySpec(
            ResearchFamily.PROCEDURE,
            ("Quelle procédure observable permet d'agir sur cette possibilité ?",),
        ),
        DeepenFamilySpec(
            ResearchFamily.ECONOMIC,
            ("Quels coûts, financements ou autres paramètres économiques observables s'appliquent ?",),
        ),
        DeepenFamilySpec(
            ResearchFamily.REFERENCE,
            ("Quelles références permettent de vérifier et d'accomplir cette possibilité ?",),
        ),
    )
)
