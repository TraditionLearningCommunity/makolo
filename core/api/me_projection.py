from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch
from django.urls import reverse

from accounts.models import UserProfile
from accounts.profile_activation import build_profile_activation_summary
from discovery.models import ActivityBookmark, DiscoveryWatch
from groups.selectors import groups_for_profile
from loyalty.selectors import get_accounts_visible_to, get_subscriptions_visible_to
from organizations.console_context import authorized_spaces
from organizations.models import (
    OrganizationFollow,
    ProfileFollow,
    TeamMembership,
    TeamMembershipStatus,
)
from partners.models import PartnerStatus
from partners.selectors import get_partners_visible_to
from personal_assets.models import PersonalAssetVersion
from personal_assets.selectors import personal_assets_for_controller
from recognition.selectors import (
    account_for_profile,
    redemptions_requiring_beneficiary_response,
)
from sharing.passport import (
    PASSPORT_COMPLETE,
    PASSPORT_CUSTOM,
    PASSPORT_PUBLIC,
    PASSPORT_THEMATIC,
    PASSPORT_VARIANTS,
    build_profile_passport,
)
from topics.models import ProfileInterest, ProfileOpenTo
from trust.credential_selectors import credentials_for_profile
from trust.selectors import proofs_for_profile


ME_PREVIEW_LIMIT = 6
ME_SECTION_LIMIT = 50


def _clean_text(value):
    if value is None:
        return None
    value = str(value).strip()
    return value or None


def _profile_extension(profile):
    """Read the optional one-to-one Profile extension without writing on GET."""
    try:
        return profile.profile
    except ObjectDoesNotExist:
        return UserProfile(user=profile)


def _avatar_url(profile, request):
    if not profile.avatar:
        return None
    url = profile.avatar.url
    return request.build_absolute_uri(url) if request is not None else url


def _display_name(profile):
    return _clean_text(profile.full_name) or _clean_text(profile.username) or str(profile.pk)


def _activation_payload(profile, profile_extension):
    summary = build_profile_activation_summary(profile, profile=profile_extension)
    next_step = summary.next_step
    return {
        "percentage": summary.percentage,
        "completed_steps": summary.completed_steps,
        "available_steps": summary.available_steps,
        "is_complete": summary.is_complete,
        "next_step": (
            {
                "key": next_step.key,
                "label": next_step.label,
                "summary": next_step.next_copy or None,
            }
            if next_step is not None
            else None
        ),
    }


def _bounded(queryset, serializer, *, limit):
    total = queryset.count()
    rows = list(queryset[:limit])
    return {
        "count": total,
        "items": [serializer(row) for row in rows],
        "has_more": total > len(rows),
    }


def _identity_payload(profile, request=None):
    profile_extension = _profile_extension(profile)
    city = _clean_text(profile_extension.city)
    country = _clean_text(profile_extension.country)
    location = {"city": city, "country": country} if city or country else None
    return {
        "kind": "profile",
        "id": str(profile.pk),
        "display_name": _display_name(profile),
        "avatar_url": _avatar_url(profile, request),
        "bio": _clean_text(profile.bio),
        "profession": _clean_text(profile_extension.profession),
        "location": location,
        "presence": {
            "public_profile": bool(profile_extension.public_profile),
            "searchable": bool(profile_extension.searchable),
        },
        "activation": _activation_payload(profile, profile_extension),
        "capabilities": ["edit_identity"],
    }


def _interest_item(row):
    return {
        "id": str(row.pk),
        "topic": {
            "id": str(row.topic_id),
            "code": row.topic.code,
            "label": row.topic.label,
        },
        "public": bool(row.is_public),
    }


def _open_to_item(row):
    topic = None
    if row.topic_id:
        topic = {
            "id": str(row.topic_id),
            "code": row.topic.code,
            "label": row.topic.label,
        }
    return {
        "id": str(row.pk),
        "kind": row.kind,
        "label": row.get_kind_display(),
        "topic": topic,
        "public": bool(row.is_public),
        "searchable": bool(row.is_searchable),
    }


def _watch_item(row):
    dossier = None
    if row.dossier_id:
        dossier = {
            "kind": "dossier",
            "id": str(row.dossier_id),
            "title": row.dossier.title,
        }
    return {
        "id": str(row.pk),
        "name": row.name,
        "status": row.status,
        "status_label": row.get_status_display(),
        "dossier": dossier,
        "updated_at": row.updated_at,
    }


def _bookmark_item(row):
    return {
        "id": str(row.pk),
        "activity": {
            "kind": "activity",
            "id": str(row.activity_id),
            "title": row.activity.title,
        },
        "created_at": row.created_at,
    }


def _space_follow_item(row):
    return {
        "id": str(row.pk),
        "space": {
            "kind": "space",
            "id": str(row.organization_id),
            "name": row.organization.name,
            "slug": row.organization.slug,
        },
        "followed_at": row.followed_at,
    }


def _profile_follow_item(row):
    target = row.organizer_profile
    return {
        "id": str(row.pk),
        "profile": {
            "kind": "profile",
            "id": str(target.pk),
            "display_name": _display_name(target),
        },
        "followed_at": row.followed_at,
    }


def build_personal_considerations_data(profile, *, limit=ME_SECTION_LIMIT):
    """Private facts explicitly chosen by the Profile; no inferred preference."""
    interests = (
        ProfileInterest.objects.filter(profile=profile, topic__is_active=True)
        .select_related("topic")
        .order_by("topic__label", "created_at", "id")
    )
    open_to = (
        ProfileOpenTo.objects.filter(profile=profile, is_active=True)
        .select_related("topic")
        .order_by("kind", "topic__label", "created_at", "id")
    )
    watches = (
        DiscoveryWatch.objects.filter(owner=profile)
        .select_related("dossier")
        .order_by("-updated_at", "id")
    )
    bookmarks = (
        ActivityBookmark.objects.filter(user=profile)
        .select_related("activity")
        .order_by("-created_at", "id")
    )
    followed_spaces = (
        OrganizationFollow.objects.filter(user=profile)
        .select_related("organization")
        .order_by("-followed_at", "id")
    )
    followed_profiles = (
        ProfileFollow.objects.filter(user=profile)
        .select_related("organizer_profile")
        .order_by("-followed_at", "id")
    )
    return {
        "interests": _bounded(interests, _interest_item, limit=limit),
        "open_to": _bounded(open_to, _open_to_item, limit=limit),
        "watches": _bounded(watches, _watch_item, limit=limit),
        "bookmarks": _bounded(bookmarks, _bookmark_item, limit=limit),
        "followed_spaces": _bounded(followed_spaces, _space_follow_item, limit=limit),
        "followed_profiles": _bounded(followed_profiles, _profile_follow_item, limit=limit),
    }


def _authorized_space_item(space):
    return {
        "kind": "space",
        "id": str(space.pk),
        "name": space.name,
        "slug": space.slug,
        "relationship": "authorized_context",
        "can_act": True,
    }


def _team_membership_item(row):
    return {
        "kind": "team",
        "id": str(row.team_id),
        "name": row.team.name,
        "space": {
            "kind": "space",
            "id": str(row.team.organization_id),
            "name": row.team.organization.name,
            "slug": row.team.organization.slug,
        },
        "relationship": "membership",
    }


def _group_item(group):
    owner = None
    if group.space_id:
        owner = {
            "kind": "space",
            "id": str(group.space_id),
            "name": group.space.name,
            "slug": group.space.slug,
        }
    elif group.owner_profile_id:
        owner = {
            "kind": "profile",
            "id": str(group.owner_profile_id),
            "display_name": _display_name(group.owner_profile),
        }
    return {
        "kind": "group",
        "id": str(group.pk),
        "name": group.name,
        "slug": group.slug,
        "owner": owner,
        "active_member_count": int(getattr(group, "active_member_count", 0) or 0),
    }


def build_personal_collectives_data(profile, *, limit=ME_SECTION_LIMIT):
    """Compose relationships without treating membership as authority."""
    spaces = authorized_spaces(profile).order_by("name", "id")
    team_memberships = (
        TeamMembership.objects.filter(
            user=profile,
            status=TeamMembershipStatus.ACTIVE,
            team__is_active=True,
        )
        .select_related("team__organization")
        .order_by("team__organization__name", "team__name", "id")
    )
    groups = groups_for_profile(profile).order_by("name", "id")
    return {
        "authorized_spaces": _bounded(spaces, _authorized_space_item, limit=limit),
        "teams": _bounded(team_memberships, _team_membership_item, limit=limit),
        "groups": _bounded(groups, _group_item, limit=limit),
    }


def _asset_item(asset):
    versions = getattr(asset, "_z4_versions", ())
    latest = versions[0] if versions else None
    latest_payload = None
    if latest is not None:
        latest_payload = {
            "version": latest.version,
            "issued_at": latest.issued_at,
            "expires_at": latest.expires_at,
            "created_at": latest.created_at,
        }
    return {
        "kind": "personal_asset",
        "id": str(asset.pk),
        "title": asset.title,
        "asset_kind": asset.kind,
        "asset_kind_label": asset.get_kind_display(),
        "sensitivity": asset.sensitivity,
        "sensitivity_label": asset.get_sensitivity_display(),
        "latest_version": latest_payload,
    }


def _proof_item(proof):
    return {
        "kind": "proof",
        "id": str(proof.pk),
        "proof_type": proof.proof_type,
        "proof_type_label": proof.get_proof_type_display(),
        "status": proof.status,
        "status_label": proof.get_status_display(),
        "issued_at": proof.issued_at,
        "activity": {
            "kind": "activity",
            "id": str(proof.journey.activity_id),
            "title": proof.journey.activity.title,
        },
        "occurrence_id": str(proof.occurrence_id) if proof.occurrence_id else None,
    }


def _credential_item(credential):
    issuer = None
    if credential.issuer_space_id:
        issuer = {
            "kind": "space",
            "id": str(credential.issuer_space_id),
            "name": credential.issuer_space.name,
        }
    elif credential.issuer_profile_id:
        issuer = {
            "kind": "profile",
            "id": str(credential.issuer_profile_id),
            "display_name": _display_name(credential.issuer_profile),
        }
    return {
        "kind": "credential",
        "id": str(credential.pk),
        "title": credential.title,
        "credential_type": credential.credential_type,
        "credential_type_label": credential.get_credential_type_display(),
        "status": credential.status,
        "status_label": credential.get_status_display(),
        "issued_at": credential.issued_at,
        "issuer": issuer,
        "activity": {
            "kind": "activity",
            "id": str(credential.activity_id),
            "title": credential.activity.title,
        },
    }


def build_personal_resources_data(profile, *, limit=ME_SECTION_LIMIT):
    versions = PersonalAssetVersion.objects.order_by("-version", "-created_at")
    assets = (
        personal_assets_for_controller(profile)
        .prefetch_related(Prefetch("versions", queryset=versions, to_attr="_z4_versions"))
        .order_by("-updated_at", "id")
    )
    proofs = proofs_for_profile(profile)
    credentials = credentials_for_profile(profile)
    return {
        "documents": _bounded(assets, _asset_item, limit=limit),
        "proofs": _bounded(proofs, _proof_item, limit=limit),
        "credentials": _bounded(credentials, _credential_item, limit=limit),
    }


def _passport_interest(row):
    return {
        "id": str(row.pk),
        "topic": {"code": row.topic.code, "label": row.topic.label},
        "public": bool(row.is_public),
    }


def _passport_open_to(row):
    return {
        "id": str(row.pk),
        "kind": row.kind,
        "label": row.get_kind_display(),
        "topic": (
            {"code": row.topic.code, "label": row.topic.label}
            if row.topic_id
            else None
        ),
        "public": bool(row.is_public),
        "searchable": bool(row.is_searchable),
    }


def _passport_activity(activity):
    return {
        "kind": "activity",
        "id": str(activity.pk),
        "title": activity.title,
        "status": activity.status,
        "visibility": activity.visibility,
    }


def _passport_proof(proof):
    return _proof_item(proof)


def _passport_credential(credential):
    return _credential_item(credential)


def build_personal_passport_data(
    profile,
    *,
    variant=PASSPORT_COMPLETE,
    topic_codes=(),
    selected_activity_ids=None,
    selected_proof_ids=None,
    selected_credential_ids=None,
    selected_sections=None,
):
    if variant not in PASSPORT_VARIANTS:
        raise ValueError("Variante Passeport inconnue.")

    projection = build_profile_passport(
        profile,
        variant=variant,
        topic_codes=topic_codes,
        selected_activity_ids=selected_activity_ids,
        selected_proof_ids=selected_proof_ids,
        selected_credential_ids=selected_credential_ids,
        selected_sections=selected_sections,
    )
    identity = dict(projection.identity)
    identity["links"] = [
        {"label": label, "url": url}
        for label, url in projection.identity.get("links", ())
    ]
    return {
        "variant": projection.variant,
        "identity": identity,
        "declared": {
            "interests": [_passport_interest(row) for row in projection.interests],
            "open_to": [_passport_open_to(row) for row in projection.open_to],
        },
        "activities": [_passport_activity(row) for row in projection.activities],
        "established": {
            "proofs": [_passport_proof(row) for row in projection.proofs],
        },
        "issued": {
            "credentials": [_passport_credential(row) for row in projection.credentials],
        },
        "topics": [
            {"id": str(topic.pk), "code": topic.code, "label": topic.label}
            for topic in projection.topics
        ],
    }


def _partner_item(partner):
    return {
        "kind": "partner_relationship",
        "id": str(partner.pk),
        "name": partner.display_name,
        "partner_kind": partner.kind,
        "partner_kind_label": partner.get_kind_display(),
        "status": partner.status,
        "status_label": partner.get_status_display(),
        "space": {
            "kind": "space",
            "id": str(partner.organization_id),
            "name": partner.organization.name,
            "slug": partner.organization.slug,
        },
    }


def build_personal_partners_data(profile, *, limit=ME_SECTION_LIMIT):
    relationships = (
        get_partners_visible_to(profile)
        .filter(user=profile)
        .select_related("organization")
        .order_by("organization__name", "name", "id")
    )
    return {
        "relationships": _bounded(relationships, _partner_item, limit=limit),
        "links": {
            "domain_api": "/api/v1/partners/partners/",
        },
    }


def _support_summary(profile):
    recognition_account = account_for_profile(profile)
    incoming_recognition = redemptions_requiring_beneficiary_response(profile).exists()

    loyalty_accounts = get_accounts_visible_to(profile).filter(user=profile)
    loyalty_subscriptions = get_subscriptions_visible_to(profile).filter(user=profile)
    loyalty_available = loyalty_accounts.exists() or loyalty_subscriptions.exists()

    personal_partners = get_partners_visible_to(profile).filter(
        user=profile,
        status=PartnerStatus.ACTIVE,
    )
    return {
        "recognition": {
            "available": recognition_account is not None or incoming_recognition,
            "needs_response": incoming_recognition,
            "points_balance": (
                recognition_account.points_balance
                if recognition_account is not None
                else 0
            ),
            "links": {"api": "/api/v1/recognition/me/"},
        },
        "loyalty": {
            "available": loyalty_available,
            "account_count": loyalty_accounts.count(),
            "subscription_count": loyalty_subscriptions.count(),
            "links": {"api": "/api/v1/loyalty/me/"},
        },
        "partners": {
            "available": personal_partners.exists(),
            "count": personal_partners.count(),
            "links": {"api": reverse("personal-projections:partners")},
        },
    }


def build_personal_me_data(*, profile, request=None):
    """Compose the Mature personal Moi surface from owner-domain read models."""
    return {
        "identity": _identity_payload(profile, request),
        "passport": {
            "available": True,
            "links": {"api": reverse("personal-projections:passport")},
        },
        "considerations": build_personal_considerations_data(
            profile,
            limit=ME_PREVIEW_LIMIT,
        ),
        "collectives": build_personal_collectives_data(
            profile,
            limit=ME_PREVIEW_LIMIT,
        ),
        "resources": build_personal_resources_data(
            profile,
            limit=ME_PREVIEW_LIMIT,
        ),
        "support": _support_summary(profile),
        "links": {
            "self": reverse("personal-projections:me"),
            "identity_update": reverse("profile-update"),
            "considerations": reverse("personal-projections:considerations"),
            "collectives": reverse("personal-projections:collectives"),
            "passport": reverse("personal-projections:passport"),
            "resources": reverse("personal-projections:resources"),
            "partners": reverse("personal-projections:partners"),
            "accesses": reverse("personal-projections:accesses"),
            "history": reverse("personal-projections:history"),
        },
    }
