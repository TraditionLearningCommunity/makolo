from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping, Optional, Sequence, Tuple

from .canonicalization import canonicalize_locator
from .contracts import ProspectingCandidate, ProspectingEvidence, ProspectingTarget
from .errors import ExpansionContractError, ProspectorContractError
from .observation_contracts import (
    ObservationReport,
    ObservationStatus,
    ObservedReference,
)
from .policy import DEFAULT_SENSITIVE_QUERY_NAMES
from .traps import inspect_web_url

WEB_GRAPH_RELATIONS = frozenset(
    {
        "link",
        "redirect",
        "redirect_final",
        "canonical",
        "alternate",
    }
)
SITEMAP_RELATIONS = frozenset(
    {
        "sitemap",
        "sitemap_index",
        "sitemap_entry",
    }
)
FEED_RELATIONS = frozenset(
    {
        "feed",
        "feed_entry",
    }
)
RELATION_FAMILIES = {
    **{relation: "web_graph" for relation in WEB_GRAPH_RELATIONS},
    **{relation: "sitemap" for relation in SITEMAP_RELATIONS},
    **{relation: "feed" for relation in FEED_RELATIONS},
}

TECHNICAL_REFERENCE_ATTRIBUTES = frozenset(
    {
        "media_type",
        "hreflang",
        "rel",
        "type",
    }
)


def _positive_int(name: str, value: int, *, allow_zero: bool = False) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProspectorContractError(f"{name} must be an integer")
    minimum = 0 if allow_zero else 1
    if value < minimum:
        qualifier = "non-negative" if allow_zero else "positive"
        raise ProspectorContractError(f"{name} must be a {qualifier} integer")
    return value


def _frozen_counts(value: Mapping[str, int]) -> Mapping[str, int]:
    return MappingProxyType(dict(value))


def _safe_technical_scalar(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return None


@dataclass(frozen=True, slots=True)
class ExpansionPolicy:
    max_depth: int
    max_references_per_report: int
    max_candidates_per_report: int
    max_same_host_candidates: int
    max_cross_host_candidates: int
    max_unique_cross_hosts: int
    max_per_host_candidates: int
    max_per_url_shape: int
    max_query_parameters: int
    max_path_segments: int
    allowed_families: Tuple[str, ...] = ("web_graph", "sitemap", "feed")
    technical_attribute_names: Tuple[str, ...] = tuple(
        sorted(TECHNICAL_REFERENCE_ATTRIBUTES)
    )
    sensitive_query_names: Tuple[str, ...] = DEFAULT_SENSITIVE_QUERY_NAMES

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "max_depth",
            _positive_int("max_depth", self.max_depth, allow_zero=True),
        )
        for name in (
            "max_references_per_report",
            "max_candidates_per_report",
            "max_same_host_candidates",
            "max_cross_host_candidates",
            "max_unique_cross_hosts",
            "max_per_host_candidates",
            "max_per_url_shape",
            "max_query_parameters",
            "max_path_segments",
        ):
            object.__setattr__(
                self,
                name,
                _positive_int(name, getattr(self, name)),
            )

        allowed = tuple(dict.fromkeys(str(value).strip() for value in self.allowed_families))
        if not allowed or any(not value for value in allowed):
            raise ProspectorContractError("allowed_families must not contain blanks")
        unsupported = sorted(set(allowed) - {"web_graph", "sitemap", "feed"})
        if unsupported:
            raise ProspectorContractError(
                f"unsupported expansion family {unsupported[0]!r}"
            )
        object.__setattr__(self, "allowed_families", allowed)

        attributes = tuple(
            dict.fromkeys(str(value).strip() for value in self.technical_attribute_names)
        )
        if any(not value for value in attributes):
            raise ProspectorContractError(
                "technical_attribute_names must not contain blanks"
            )
        object.__setattr__(self, "technical_attribute_names", attributes)

        sensitive = tuple(
            dict.fromkeys(str(value).strip().lower() for value in self.sensitive_query_names)
        )
        if any(not value for value in sensitive):
            raise ProspectorContractError(
                "sensitive_query_names must not contain blanks"
            )
        object.__setattr__(self, "sensitive_query_names", sensitive)

    @property
    def fingerprint(self) -> str:
        payload = {
            "max_depth": self.max_depth,
            "max_references_per_report": self.max_references_per_report,
            "max_candidates_per_report": self.max_candidates_per_report,
            "max_same_host_candidates": self.max_same_host_candidates,
            "max_cross_host_candidates": self.max_cross_host_candidates,
            "max_unique_cross_hosts": self.max_unique_cross_hosts,
            "max_per_host_candidates": self.max_per_host_candidates,
            "max_per_url_shape": self.max_per_url_shape,
            "max_query_parameters": self.max_query_parameters,
            "max_path_segments": self.max_path_segments,
            "allowed_families": self.allowed_families,
            "technical_attribute_names": self.technical_attribute_names,
            "sensitive_query_names": self.sensitive_query_names,
        }
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ExpansionResult:
    observation_ref: str
    policy_fingerprint: str
    considered: int
    admitted: int
    candidate_keys: Tuple[str, ...] = ()
    skip_counts: Mapping[str, int] = field(default_factory=dict)
    truncated_references: int = 0

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_keys",
            tuple(self.candidate_keys),
        )
        object.__setattr__(
            self,
            "skip_counts",
            _frozen_counts(self.skip_counts),
        )


class ObservationExpansionSink:
    """Turns structure-only Observateur reports into bounded Frontier candidates."""

    def __init__(self, *, frontier, lookup, policy: ExpansionPolicy) -> None:
        self.frontier = frontier
        self.lookup = lookup
        self.policy = policy

    async def submit_report(self, report: ObservationReport) -> ExpansionResult:
        if not isinstance(report, ObservationReport):
            raise ExpansionContractError("report must be an ObservationReport")

        if report.status is not ObservationStatus.OBSERVED:
            return ExpansionResult(
                observation_ref=report.observation_ref,
                policy_fingerprint=self.policy.fingerprint,
                considered=0,
                admitted=0,
            )

        parent = await self.lookup.get(report.target_key)
        if parent is None:
            raise ExpansionContractError(
                f"source target {report.target_key!r} is missing from Frontier"
            )

        parent_depth = parent.policy_context.get("depth", 0)
        if (
            not isinstance(parent_depth, int)
            or isinstance(parent_depth, bool)
            or parent_depth < 0
        ):
            raise ExpansionContractError("parent depth must be a non-negative integer")

        child_depth = parent_depth + 1
        references = list(report.references)

        if report.final_locator and report.final_locator != report.requested_locator:
            references.insert(
                0,
                ObservedReference(
                    relation="redirect_final",
                    locator=report.final_locator,
                    discovered_at=report.observed_at,
                ),
            )

        truncated = max(
            0,
            len(references) - self.policy.max_references_per_report,
        )
        references = references[: self.policy.max_references_per_report]

        if child_depth > self.policy.max_depth:
            return ExpansionResult(
                observation_ref=report.observation_ref,
                policy_fingerprint=self.policy.fingerprint,
                considered=len(references),
                admitted=0,
                skip_counts={"depth_exceeded": len(references)} if references else {},
                truncated_references=truncated,
            )

        try:
            parent_structure = inspect_web_url(parent.locator)
        except ProspectorContractError as exc:
            raise ExpansionContractError(
                "parent Frontier target is not a valid web URL"
            ) from exc

        skip = Counter()
        seen_keys = set()
        per_host = Counter()
        per_shape = Counter()
        same_host_count = 0
        cross_host_count = 0
        cross_hosts = set()
        candidate_keys = []

        for reference in references:
            if len(candidate_keys) >= self.policy.max_candidates_per_report:
                skip["candidate_budget"] += 1
                continue

            relation = reference.relation.strip().lower()
            family = RELATION_FAMILIES.get(relation)
            if family is None:
                skip["unknown_relation"] += 1
                continue
            if family not in self.policy.allowed_families:
                skip["family_disabled"] += 1
                continue
            if reference.kind != "web_url":
                skip["unsupported_kind"] += 1
                continue

            try:
                canonical = canonicalize_locator(
                    kind=reference.kind,
                    locator=reference.locator,
                )
                structure = inspect_web_url(canonical.locator)
            except ProspectorContractError:
                skip["invalid_locator"] += 1
                continue

            if canonical.target_key == parent.target_key:
                skip["self_reference"] += 1
                continue
            if canonical.target_key in seen_keys:
                skip["duplicate_reference"] += 1
                continue

            if set(structure.query_names) & set(self.policy.sensitive_query_names):
                skip["sensitive_query"] += 1
                continue
            if structure.query_parameter_count > self.policy.max_query_parameters:
                skip["query_parameter_limit"] += 1
                continue
            if structure.path_segment_count > self.policy.max_path_segments:
                skip["path_segment_limit"] += 1
                continue
            if per_shape[structure.shape] >= self.policy.max_per_url_shape:
                skip["url_shape_limit"] += 1
                continue
            if per_host[structure.host] >= self.policy.max_per_host_candidates:
                skip["per_host_limit"] += 1
                continue

            same_host = structure.host == parent_structure.host
            if same_host:
                if same_host_count >= self.policy.max_same_host_candidates:
                    skip["same_host_limit"] += 1
                    continue
            else:
                if cross_host_count >= self.policy.max_cross_host_candidates:
                    skip["cross_host_limit"] += 1
                    continue
                if (
                    structure.host not in cross_hosts
                    and len(cross_hosts) >= self.policy.max_unique_cross_hosts
                ):
                    skip["unique_cross_host_limit"] += 1
                    continue

            attributes = {
                "relation": relation,
                "source_handoff_generation": report.handoff_generation,
                "expansion_policy_fingerprint": self.policy.fingerprint,
            }
            for name in self.policy.technical_attribute_names:
                if name in reference.attributes:
                    value = _safe_technical_scalar(reference.attributes[name])
                    if value is not None:
                        attributes[name] = value

            policy_context = dict(parent.policy_context)
            policy_context["depth"] = child_depth

            observation_hints = {
                "discovery_relation": relation,
                "discovery_family": family,
            }
            media_type = reference.attributes.get("media_type")
            if isinstance(media_type, str) and media_type.strip():
                observation_hints["referenced_media_type"] = media_type.strip()

            candidate = ProspectingCandidate(
                locator=canonical.locator,
                kind=canonical.kind,
                evidence=(
                    ProspectingEvidence(
                        method=family,
                        discovered_at=reference.discovered_at,
                        source_target_key=parent.target_key,
                        source_observation_ref=report.observation_ref,
                        attributes=attributes,
                    ),
                ),
                policy_context=policy_context,
                observation_hints=observation_hints,
            )
            admitted = await self.frontier.admit(candidate)

            seen_keys.add(canonical.target_key)
            per_host[structure.host] += 1
            per_shape[structure.shape] += 1
            if same_host:
                same_host_count += 1
            else:
                cross_host_count += 1
                cross_hosts.add(structure.host)
            candidate_keys.append(admitted.target_key)

        return ExpansionResult(
            observation_ref=report.observation_ref,
            policy_fingerprint=self.policy.fingerprint,
            considered=len(references),
            admitted=len(candidate_keys),
            candidate_keys=tuple(candidate_keys),
            skip_counts=dict(skip),
            truncated_references=truncated,
        )
