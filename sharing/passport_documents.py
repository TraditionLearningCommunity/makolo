from __future__ import annotations

import hashlib
import json

from django.core import signing

from .models import PassportSnapshot, PublicIdentifier, PublicSubjectKind


PASSPORT_VERIFY_SALT = "sharing.passport.verify.v1"


def _iso(value):
    return value.isoformat() if value else None


def serialize_passport_projection(projection):
    """Serialize only the facts rendered by one issued Passport document."""

    return {
        "schema_version": 1,
        "subject_kind": projection.subject_kind,
        "variant": projection.variant,
        "generated_at": _iso(projection.generated_at),
        "identity": {
            "name": projection.identity.get("name", ""),
            "bio": projection.identity.get("bio", ""),
            "profession": projection.identity.get("profession", ""),
            "location": projection.identity.get("location", ""),
            "links": list(projection.identity.get("links", ())),
        },
        "interests": [row.topic.label for row in projection.interests],
        "open_to": [
            {
                "kind": row.get_kind_display(),
                "topic": row.topic.label if row.topic else "",
            }
            for row in projection.open_to
        ],
        "activities": [
            {
                "id": str(row.pk),
                "title": row.title,
                "status": row.get_status_display(),
                "visibility": row.get_visibility_display(),
            }
            for row in projection.activities
        ],
        "proofs": [
            {
                "public_id": str(row.public_id),
                "label": row.get_proof_type_display(),
                "activity": row.journey.activity.title,
                "issued_at": _iso(row.issued_at),
            }
            for row in projection.proofs
        ],
        "credentials": [
            {
                "public_id": str(row.public_id),
                "title": row.title,
                "type": row.get_credential_type_display(),
                "issuer": row.issuer_display_name,
                "status": row.get_status_display(),
                "issued_at": _iso(row.issued_at),
            }
            for row in projection.credentials
        ],
        "trust_verifications": [
            {
                "label": row.get_claim_type_display(),
                "valid_until": _iso(row.valid_until),
            }
            for row in projection.trust_verifications
        ],
        "credential_summary": list(projection.credential_summary),
        "topics": [{"code": row.code, "label": row.label} for row in projection.topics],
    }


def issue_passport_snapshot(projection):
    if projection.subject_kind == PublicSubjectKind.PROFILE:
        record = PublicIdentifier.objects.get(profile=projection.subject)
        subject_kwargs = {"profile": projection.subject, "space": None}
    else:
        record = PublicIdentifier.objects.get(space=projection.subject)
        subject_kwargs = {"profile": None, "space": projection.subject}

    payload = serialize_passport_projection(projection)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return PassportSnapshot.objects.create(
        subject_kind=projection.subject_kind,
        public_identifier=record.identifier,
        variant=projection.variant,
        payload=payload,
        payload_hash=digest,
        generated_at=projection.generated_at,
        **subject_kwargs,
    )


def passport_verification_token(snapshot):
    return signing.dumps(
        {"passport_id": str(snapshot.pk)},
        salt=PASSPORT_VERIFY_SALT,
        compress=True,
    )


def resolve_passport_verification_token(token):
    data = signing.loads(token, salt=PASSPORT_VERIFY_SALT)
    return PassportSnapshot.objects.select_related("profile", "space").get(pk=data["passport_id"])
