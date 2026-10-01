from __future__ import annotations

from typing import Union

from mayele.cognition import CandidateStatus, RealityCandidate, ReferentKind
from mayele.common.errors import MayeleContractError
from mayele.observation import Mention

from .contracts import (
    IdentityResolution,
    IdentityResolutionBasisKind,
)


IdentityResolutionSubject = Union[Mention, RealityCandidate]


def _expected_basis_kind(referent_kind: ReferentKind) -> IdentityResolutionBasisKind:
    if referent_kind is ReferentKind.MENTION:
        return IdentityResolutionBasisKind.MENTION
    if referent_kind is ReferentKind.REALITY_CANDIDATE:
        return IdentityResolutionBasisKind.REALITY_CANDIDATE
    raise MayeleContractError("a resolved Reality does not require identity resolution")


def validate_identity_resolution(
    resolution: IdentityResolution,
    subject: IdentityResolutionSubject,
) -> IdentityResolution:
    """Validate MY4 lineage and scope without deciding which identity is correct."""

    if not isinstance(resolution, IdentityResolution):
        raise MayeleContractError("resolution must be IdentityResolution")

    referent = resolution.referent
    if referent.kind is ReferentKind.MENTION:
        if not isinstance(subject, Mention):
            raise MayeleContractError("MENTION resolution requires a Mention subject")
        subject_ref = subject.mention_ref
    elif referent.kind is ReferentKind.REALITY_CANDIDATE:
        if not isinstance(subject, RealityCandidate):
            raise MayeleContractError(
                "REALITY_CANDIDATE resolution requires a RealityCandidate subject"
            )
        if subject.status is CandidateStatus.REJECTED:
            raise MayeleContractError(
                "a rejected RealityCandidate cannot be promoted by identity resolution"
            )
        subject_ref = subject.candidate_ref
    else:
        raise MayeleContractError("a resolved Reality does not require identity resolution")

    if referent.ref != subject_ref:
        raise MayeleContractError("resolution referent does not match its subject")
    if (
        resolution.reality is not None
        and resolution.reality.reality_ref == referent.ref
    ):
        raise MayeleContractError(
            "identity resolution must not reuse a non-Reality referent ref as reality_ref"
        )
    if resolution.referent_scope != subject.scope:
        raise MayeleContractError("resolution referent scope must match subject scope")

    required_basis_kind = _expected_basis_kind(referent.kind)
    if not any(
        item.kind is required_basis_kind and item.ref == subject_ref
        for item in resolution.basis
    ):
        raise MayeleContractError(
            "identity resolution basis must preserve the resolved subject lineage"
        )

    return resolution
