from __future__ import annotations

from django.db.models import Q
from django.urls import reverse

from trust.credential_models import CredentialStatus, CredentialType
from trust.credential_selectors import credentials_for_profile
from trust.models import ProofStatus, ProofType
from trust.selectors import proofs_for_profile


TRUST_RESOURCE_DEFAULT_LIMIT = 24
TRUST_RESOURCE_MAX_LIMIT = 50
TRUST_RESOURCE_MAX_QUERY = 120
TRUST_RESOURCE_SORT_VALUES = frozenset({"recent", "oldest", "title"})
PROOF_STATUS_VALUES = frozenset({"all", *ProofStatus.values})
PROOF_TYPE_VALUES = frozenset(ProofType.values)
CREDENTIAL_STATUS_VALUES = frozenset({"all", *CredentialStatus.values})
CREDENTIAL_TYPE_VALUES = frozenset(CredentialType.values)


def _proof_type_matches(query):
    needle = query.casefold()
    return [
        value
        for value, label in ProofType.choices
        if needle in label.casefold() or needle in value.casefold()
    ]


def _credential_type_matches(query):
    needle = query.casefold()
    return [
        value
        for value, label in CredentialType.choices
        if needle in label.casefold() or needle in value.casefold()
    ]


def _occurrence_payload(occurrence):
    if occurrence is None:
        return None
    return {
        "id": str(occurrence.pk),
        "label": occurrence.label or None,
        "start_date": occurrence.start_date,
        "start_time": occurrence.start_time,
        "timezone": occurrence.timezone,
    }


def _proof_payload(proof, *, detail=False):
    links = {
        "detail": reverse("personal-projections:proof-detail", kwargs={"pk": proof.pk}),
        "journey": reverse(
            "core:participant-journey-detail",
            kwargs={"pk": proof.journey_id},
        ),
    }
    capabilities = ["view_detail", "open_journey"]
    if proof.status == ProofStatus.ACTIVE:
        links["passport"] = reverse("personal-projections:passport")
        links["passport_web"] = reverse("sharing:passport-me")
        capabilities.append("open_passport")
    if proof.is_public:
        links["verify"] = reverse(
            "trust:proof-verify",
            kwargs={"public_id": proof.public_id},
        )
        capabilities.append("verify_publicly")

    payload = {
        "kind": "proof",
        "id": str(proof.pk),
        "public_id": str(proof.public_id),
        "proof_type": proof.proof_type,
        "proof_type_label": proof.get_proof_type_display(),
        "status": proof.status,
        "status_label": proof.get_status_display(),
        "is_public": bool(proof.is_public),
        "issued_at": proof.issued_at,
        "revoked_at": proof.revoked_at,
        "activity": {
            "kind": "activity",
            "id": str(proof.journey.activity_id),
            "title": proof.journey.activity.title,
        },
        "journey": {
            "kind": "journey",
            "id": str(proof.journey_id),
        },
        "occurrence": _occurrence_payload(proof.occurrence),
        "capabilities": capabilities,
        "links": links,
    }
    if detail:
        payload["revocation"] = {
            "revoked_at": proof.revoked_at,
            "reason": proof.revoke_reason or None,
        }
    return payload


def build_personal_proofs_collection(
    profile,
    *,
    query="",
    status="all",
    proof_type="",
    sort="recent",
    limit=TRUST_RESOURCE_DEFAULT_LIMIT,
    offset=0,
):
    query = (query or "").strip()
    queryset = proofs_for_profile(profile)
    if query:
        queryset = queryset.filter(
            Q(journey__activity__title__icontains=query)
            | Q(proof_type__in=_proof_type_matches(query))
        )
    if status != "all":
        queryset = queryset.filter(status=status)
    if proof_type:
        queryset = queryset.filter(proof_type=proof_type)

    if sort == "oldest":
        queryset = queryset.order_by("issued_at", "id")
    elif sort == "title":
        queryset = queryset.order_by("proof_type", "journey__activity__title", "id")
    else:
        queryset = queryset.order_by("-issued_at", "id")

    total = queryset.count()
    rows = list(queryset[offset : offset + limit])
    return {
        "kind": "proof_collection",
        "count": total,
        "query": query or None,
        "status": status,
        "proof_type": proof_type or None,
        "sort": sort,
        "filter_options": {
            "types": [
                {"id": value, "label": label}
                for value, label in ProofType.choices
            ],
        },
        "items": [_proof_payload(row) for row in rows],
        "page": {
            "count": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(rows) < total,
        },
        "links": {
            "self": reverse("personal-projections:proofs"),
        },
    }


def build_personal_proof_detail(profile, *, proof_id):
    proof = proofs_for_profile(profile).filter(pk=proof_id).first()
    if proof is None:
        return None
    return _proof_payload(proof, detail=True)


def _credential_issuer(credential):
    if credential.issuer_space_id:
        return {
            "kind": "space",
            "id": str(credential.issuer_space_id),
            "name": credential.issuer_space.name,
        }
    return {
        "kind": "profile",
        "id": str(credential.issuer_profile_id),
        "name": credential.issuer_display_name,
    }


def _credential_payload(credential, *, detail=False):
    links = {
        "detail": reverse(
            "personal-projections:title-detail",
            kwargs={"pk": credential.pk},
        ),
        "verify": reverse(
            "trust:credential-verify",
            kwargs={"public_id": credential.public_id},
        ),
    }
    capabilities = ["view_detail", "verify_publicly", "open_passport"]
    links["passport"] = reverse("personal-projections:passport")
    links["passport_web"] = reverse("sharing:passport-me")
    if credential.journey_id:
        links["journey"] = reverse(
            "core:participant-journey-detail",
            kwargs={"pk": credential.journey_id},
        )
        capabilities.append("open_journey")

    payload = {
        "kind": "credential",
        "id": str(credential.pk),
        "public_id": str(credential.public_id),
        "title": credential.title,
        "credential_type": credential.credential_type,
        "credential_type_label": credential.get_credential_type_display(),
        "status": credential.status,
        "status_label": (
            "Valide"
            if credential.status == CredentialStatus.ISSUED
            else "Révoqué"
        ),
        "verification_state": credential.verification_state,
        "issued_at": credential.issued_at,
        "revoked_at": credential.revoked_at,
        "issuer": _credential_issuer(credential),
        "activity": {
            "kind": "activity",
            "id": str(credential.activity_id),
            "title": credential.activity.title,
        },
        "journey": (
            {"kind": "journey", "id": str(credential.journey_id)}
            if credential.journey_id
            else None
        ),
        "occurrence": _occurrence_payload(credential.occurrence),
        "capabilities": capabilities,
        "links": links,
    }
    if detail:
        payload["statement"] = credential.statement or None
        payload["beneficiary"] = {
            "id": str(credential.subject_profile_id),
            "name": credential.subject_display_name,
        }
        payload["revocation"] = {
            "revoked_at": credential.revoked_at,
            "reason": credential.revoke_reason or None,
        }
    return payload


def build_personal_titles_collection(
    profile,
    *,
    query="",
    status="all",
    credential_type="",
    sort="recent",
    limit=TRUST_RESOURCE_DEFAULT_LIMIT,
    offset=0,
):
    query = (query or "").strip()
    queryset = credentials_for_profile(profile)
    if query:
        type_matches = _credential_type_matches(query)
        queryset = queryset.filter(
            Q(title__icontains=query)
            | Q(activity__title__icontains=query)
            | Q(issuer_space__name__icontains=query)
            | Q(issuer_profile__first_name__icontains=query)
            | Q(issuer_profile__last_name__icontains=query)
            | Q(issuer_profile__username__icontains=query)
            | Q(credential_type__in=type_matches)
        )
    if status != "all":
        queryset = queryset.filter(status=status)
    if credential_type:
        queryset = queryset.filter(credential_type=credential_type)

    if sort == "oldest":
        queryset = queryset.order_by("issued_at", "id")
    elif sort == "title":
        queryset = queryset.order_by("title", "id")
    else:
        queryset = queryset.order_by("-issued_at", "id")

    total = queryset.count()
    rows = list(queryset[offset : offset + limit])
    return {
        "kind": "credential_collection",
        "count": total,
        "query": query or None,
        "status": status,
        "credential_type": credential_type or None,
        "sort": sort,
        "filter_options": {
            "types": [
                {"id": value, "label": label}
                for value, label in CredentialType.choices
            ],
        },
        "items": [_credential_payload(row) for row in rows],
        "page": {
            "count": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(rows) < total,
        },
        "links": {
            "self": reverse("personal-projections:titles"),
        },
    }


def build_personal_title_detail(profile, *, credential_id):
    credential = credentials_for_profile(profile).filter(pk=credential_id).first()
    if credential is None:
        return None
    return _credential_payload(credential, detail=True)
