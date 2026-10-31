from __future__ import annotations

import hashlib
import hmac
import json

from django.core import signing

from .models import PassportSnapshot, PublicIdentifier, PublicSubjectKind
from .passport import PASSPORT_PUBLIC, profile_has_public_passport, space_has_public_passport


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
            "company_name": projection.identity.get("company_name", ""),
            "organization_name": projection.identity.get("organization_name", ""),
            "location": projection.identity.get("location", ""),
            "links": list(projection.identity.get("links", ())),
            "owner_details": (projection.identity.get("owner_details", {})
                              if projection.variant == "complete" else {}),
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
        "team_affiliations": list(projection.team_affiliations),
        "group_affiliations": list(projection.group_affiliations),
        "authorized_space_affiliations": list(projection.authorized_space_affiliations),
        "active_space_mandates": list(projection.active_space_mandates),
        "space_teams": list(projection.space_teams),
        "topics": [{"code": row.code, "label": row.label} for row in projection.topics],
    }


def profile_public_snapshot_still_disclosable(snapshot):
    """An issued public document cannot bypass current personal disclosure.

    Keep historical integrity metadata, but hide dated payload if any
    previously published personal fact is no longer publicly representable.
    This does not reissue or mutate a signed document.
    """
    if snapshot.subject_kind != PublicSubjectKind.PROFILE or not snapshot.profile_id:
        return False
    from .passport import PASSPORT_PUBLIC, build_profile_passport

    current = serialize_passport_projection(build_profile_passport(
        snapshot.profile, variant=PASSPORT_PUBLIC,
    ))
    dated = snapshot.payload or {}
    identity = dated.get("identity") or {}
    current_identity = current["identity"]
    for key in (
        "name", "bio", "profession", "company_name",
        "organization_name", "location", "links",
    ):
        old = identity.get(key)
        # Older snapshots may have no value for newly introduced attributes.
        if old and old != current_identity.get(key):
            return False
    if not set(dated.get("interests") or []).issubset(set(current["interests"])):
        return False
    current_open_to = {
        (row.get("kind"), row.get("topic"))
        for row in current["open_to"]
    }
    for row in dated.get("open_to") or []:
        if (row.get("kind"), row.get("topic")) not in current_open_to:
            return False
    return True


def snapshot_payload_is_intact(snapshot):
    """Check the issued text payload without recomposing any live subject data."""
    canonical = json.dumps(
        snapshot.payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return hmac.compare_digest(digest, snapshot.payload_hash)



def issue_passport_snapshot(projection):
    if projection.subject_kind == PublicSubjectKind.PROFILE:
        record = PublicIdentifier.objects.get(profile=projection.subject)
        subject_kwargs = {"profile": projection.subject, "space": None}
    else:
        record = PublicIdentifier.objects.get(space=projection.subject)
        subject_kwargs = {"profile": None, "space": projection.subject}

    public_at_issue = bool(
        projection.variant == PASSPORT_PUBLIC
        and (
            profile_has_public_passport(projection.subject)
            if projection.subject_kind == PublicSubjectKind.PROFILE
            else space_has_public_passport(projection.subject)
        )
    )
    payload = serialize_passport_projection(projection)
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return PassportSnapshot.objects.create(
        subject_kind=projection.subject_kind,
        public_identifier=record.identifier,
        variant=projection.variant,
        public_at_issue=public_at_issue,
        payload=payload,
        payload_hash=digest,
        generated_at=projection.generated_at,
        **subject_kwargs,
    )


def passport_verification_token(snapshot):
    return signing.dumps(
        {"passport_id": str(snapshot.pk), "payload_hash": snapshot.payload_hash},
        salt=PASSPORT_VERIFY_SALT,
        compress=True,
    )


def resolve_passport_verification_token(token):
    data = signing.loads(token, salt=PASSPORT_VERIFY_SALT)
    snapshot = PassportSnapshot.objects.select_related("profile", "space").get(
        pk=data["passport_id"],
    )
    # Historical signed links originally carried only a snapshot id: keep
    # reading those. New links also bind the issued fingerprint to the token.
    issued_hash = data.get("payload_hash")
    if issued_hash is not None and not hmac.compare_digest(
        str(issued_hash), snapshot.payload_hash,
    ):
        raise signing.BadSignature("Document modifié depuis son émission.")
    return snapshot
