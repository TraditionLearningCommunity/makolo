"""Framework-independent Mayele identity-resolution contracts."""

from .contracts import (
    IdentityResolution,
    IdentityResolutionBasis,
    IdentityResolutionBasisKind,
    IdentityResolutionStatus,
)
from .gate import IdentityResolutionSubject, validate_identity_resolution

__all__ = [
    "IdentityResolution",
    "IdentityResolutionBasis",
    "IdentityResolutionBasisKind",
    "IdentityResolutionStatus",
    "IdentityResolutionSubject",
    "validate_identity_resolution",
]
