from __future__ import annotations

import hashlib
import hmac
import json

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

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
            "presentation_details": (
                projection.identity.get("presentation_details", {})
                if projection.variant != "complete" else {}
            ),
        },
        "interests": [row.topic.label for row in projection.interests],
        "open_to": [
            {
                "kind": row.get_kind_display(),
                "topic": row.topic.label if row.topic else "",
            }
            for row in projection.open_to
        ],
        "activity_involvements": list(projection.activity_involvements),
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
    from accounts.profile_visibility import ProfileVisibilityResolver
    from .passport import PASSPORT_PUBLIC, build_profile_passport

    visibility = ProfileVisibilityResolver(owner=snapshot.profile)
    current = serialize_passport_projection(build_profile_passport(
        snapshot.profile, variant=PASSPORT_PUBLIC,
    ))
    dated = snapshot.payload or {}
    identity = dated.get("identity") or {}
    # A dated Passport must retain its original wording when a biography,
    # profession or name is edited. Only a withdrawal of *disclosure* can
    # suppress public reading; comparing old text against live text would
    # incorrectly make every past edition disappear after a normal edit.
    for key in (
        "name", "bio", "profession", "company_name", "organization_name",
    ):
        if identity.get(key) and not visibility.field(key):
            return False
    published_personal = identity.get("presentation_details") or {}
    permitted_keys = {"first_name", "last_name", "username", "city", "country"}
    if not isinstance(published_personal, dict) or (
        set(published_personal) - permitted_keys
    ):
        return False
    for key, visibility_key in (
        ("first_name", "name"), ("last_name", "name"),
        ("city", "city"), ("country", "country"),
    ):
        if published_personal.get(key) and not visibility.field(visibility_key):
            return False
    if identity.get("location") and not (
        visibility.field("city") and visibility.field("country")
    ):
        # Older snapshots have one location string without per-field IDs.
        # Requiring both permissions is conservative when either is hidden.
        return False
    link_keys = {
        "Site web": "website",
        "LinkedIn": "linkedin_url",
        "Facebook": "facebook_url",
        "Instagram": "instagram_url",
        "TikTok": "tiktok_url",
        "X / Twitter": "x_url",
        "YouTube": "youtube_url",
    }
    for pair in identity.get("links") or ():
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            return False
        label = str(pair[0])
        field_key = link_keys.get(label)
        if field_key is None or not visibility.field(field_key):
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

    # Disclosure of an issued public document is still bounded by current
    # owners of Activity / Proof / Credential. Keep the historical wording,
    # but never re-expose an item made private or withdrawn after issuance.
    # IDs are stable across edits; comparing titles would incorrectly hide
    # legitimate dated versions after a harmless rename.
    for family, identifier in (
        ("activities", "id"),
        ("activity_involvements", "id"),
        ("proofs", "public_id"),
        ("credentials", "public_id"),
    ):
        visible = {
            str(row[identifier])
            for row in current.get(family) or []
            if isinstance(row, dict) and row.get(identifier)
        }
        for row in dated.get(family) or []:
            if (
                not isinstance(row, dict)
                or not row.get(identifier)
                or str(row[identifier]) not in visible
            ):
                return False
    return True



def space_public_snapshot_still_disclosable(snapshot):
    """Public verification never re-exposes withdrawn collective facts.

    Keep the immutable text of the dated document. If any represented
    Activity, public Trust claim or credential aggregate no longer meets the
    current public admission, hide the payload rather than silently edit a
    signed edition. Explicit, revocable Sharing grants are separate.
    """
    if snapshot.subject_kind != PublicSubjectKind.SPACE or not snapshot.space_id:
        return False
    if not space_has_public_passport(snapshot.space):
        return False
    from .passport import PASSPORT_PUBLIC, build_space_passport

    dated = snapshot.payload or {}
    if dated.get("variant") != PASSPORT_PUBLIC:
        return False
    if dated.get("space_teams"):
        return False
    identity = dated.get("identity")
    if not isinstance(identity, dict) or identity.get("owner_details"):
        return False

    current = serialize_passport_projection(build_space_passport(
        snapshot.space, variant=PASSPORT_PUBLIC,
    ))

    admitted_activities = {
        str(row.get("id"))
        for row in current.get("activities") or []
        if isinstance(row, dict) and row.get("id")
    }
    for item in dated.get("activities") or []:
        if (not isinstance(item, dict) or not item.get("id")
                or str(item["id"]) not in admitted_activities):
            return False

    current_claims = {
        (row.get("label"), row.get("valid_until"))
        for row in current.get("trust_verifications") or []
        if isinstance(row, dict) and row.get("label")
    }
    for item in dated.get("trust_verifications") or []:
        if (not isinstance(item, dict) or
                (item.get("label"), item.get("valid_until")) not in current_claims):
            return False

    current_credentials = {
        row["credential_type"]: row["count"]
        for row in current.get("credential_summary") or []
        if isinstance(row, dict) and row.get("credential_type")
        and isinstance(row.get("count"), int)
    }
    for item in dated.get("credential_summary") or []:
        if not isinstance(item, dict):
            return False
        key, count = item.get("credential_type"), item.get("count")
        if (not key or not isinstance(count, int) or isinstance(count, bool)
                or count < 0 or current_credentials.get(key, -1) < count):
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


@transaction.atomic
def revoke_passport_snapshot(*, snapshot, actor):
    """Withdraw an issued document, never rewriting its dated content.

    The owner (or authorized Space manager) alone can withdraw issuance.
    Every currently active Sharing grant to that document is revoked through
    Sharing's canonical service, so the history cannot show phantom grants.
    """
    if not getattr(actor, "is_authenticated", False):
        raise PermissionDenied("Révocation du Passeport non autorisée.")
    if snapshot.subject_kind == PublicSubjectKind.PROFILE:
        allowed = snapshot.profile_id == actor.pk
    else:
        from organizations.permissions import user_can_manage_organization
        allowed = bool(
            snapshot.space_id
            and user_can_manage_organization(actor, snapshot.space)
        )
    if not allowed:
        raise PermissionDenied("Révocation du Passeport non autorisée.")

    locked = (
        PassportSnapshot.objects.select_for_update()
        .select_related("space")
        .get(pk=snapshot.pk)
    )
    if locked.revoked_at is None:
        locked.revoked_at = timezone.now()
        locked.save(update_fields=["revoked_at"])
    from .services import revoke_share_link
    for grant in locked.passport_share_subjects.select_related("envelope"):
        if grant.envelope.is_active_at():
            revoke_share_link(envelope=grant.envelope, actor=None)
    return locked


def passport_verification_token(snapshot):
    """Stable signed link for one immutable document across QR and history.

    TimestampSigner embeds the *time the URL was generated*, making the QR
    URL and later history URL differ for the same snapshot. Issued document
    tokens do not expire; the snapshot's revocation, hash and disclosure gates
    remain authoritative.
    """
    return signing.Signer(salt=PASSPORT_VERIFY_SALT).sign_object(
        {"passport_id": str(snapshot.pk), "payload_hash": snapshot.payload_hash},
        compress=True,
    )


def resolve_passport_verification_token(token):
    # Prior URLs used django.core.signing.dumps (TimestampSigner, three
    # segments). Keep all already shared and printed verification links valid.
    if token.count(":") == 2:
        data = signing.loads(token, salt=PASSPORT_VERIFY_SALT)
    else:
        data = signing.Signer(salt=PASSPORT_VERIFY_SALT).unsign_object(token)
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
