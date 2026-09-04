from __future__ import annotations

from .credential_models import Credential, CredentialStatus


def _credential_queryset():
    return Credential.objects.select_related(
        "subject_profile",
        "issuer_space",
        "issuer_profile",
        "issued_by",
        "activity",
        "occurrence",
        "journey",
        "revoked_by",
    )


def credentials_for_profile(profile, *, valid_only=False):
    queryset = _credential_queryset().filter(subject_profile=profile)
    if valid_only:
        queryset = queryset.filter(status=CredentialStatus.ISSUED)
    return queryset.order_by("-issued_at", "id")


def credentials_issued_by_space(space, *, valid_only=False):
    queryset = _credential_queryset().filter(issuer_space=space)
    if valid_only:
        queryset = queryset.filter(status=CredentialStatus.ISSUED)
    return queryset.order_by("-issued_at", "id")


def credentials_issued_by_profile(profile, *, valid_only=False):
    queryset = _credential_queryset().filter(issuer_profile=profile)
    if valid_only:
        queryset = queryset.filter(status=CredentialStatus.ISSUED)
    return queryset.order_by("-issued_at", "id")


def public_credential_by_id(public_id):
    """Resolve an unlisted public verification identifier, including revoked history."""
    return _credential_queryset().filter(public_id=public_id).first()
