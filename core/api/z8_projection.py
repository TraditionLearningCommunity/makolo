from __future__ import annotations

from django.db.models import OuterRef, Subquery
from django.urls import reverse
from django.utils import timezone

from authorization.constants import PermissionCode
from groups.models import GroupMembership, GroupMembershipStatus
from groups.selectors import groups_for_profile
from groups.services import has_group_permission
from personal_assets.models import PersonalAssetVersion
from personal_assets.selectors import (
    personal_asset_for_controller,
    personal_asset_versions_for_controller,
    personal_assets_for_controller,
)
from sharing.passport import (
    PASSPORT_COMPLETE,
    PASSPORT_CUSTOM,
    PASSPORT_PUBLIC,
    PASSPORT_THEMATIC,
    PASSPORT_VARIANTS,
    profile_has_public_passport,
)

from core.api.me_projection import (
    _bounded,
    _credential_item,
    _proof_item,
    build_personal_passport_data,
)
from trust.credential_selectors import credentials_for_profile
from trust.selectors import proofs_for_profile


RESOURCE_DEFAULT_LIMIT = 24
RESOURCE_MAX_LIMIT = 50
RESOURCE_SEARCH_MAX_LENGTH = 120
RESOURCE_VERSION_DEFAULT_LIMIT = 20
RESOURCE_VERSION_MAX_LIMIT = 50


def _validity_payload(*, issued_at, expires_at, observed_at):
    today = timezone.localdate(observed_at)
    if issued_at is None and expires_at is None:
        state = "unknown"
    elif issued_at is not None and issued_at > today:
        state = "not_yet_issued"
    elif expires_at is not None and expires_at < today:
        state = "expired"
    else:
        state = "current"
    return {
        "state": state,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }


def _current_version_annotations(queryset):
    latest = PersonalAssetVersion.objects.filter(asset_id=OuterRef("pk")).order_by(
        "-version",
        "-created_at",
    )
    return queryset.annotate(
        current_version_id=Subquery(latest.values("pk")[:1]),
        current_version_number=Subquery(latest.values("version")[:1]),
        current_version_issued_at=Subquery(latest.values("issued_at")[:1]),
        current_version_expires_at=Subquery(latest.values("expires_at")[:1]),
        current_version_created_at=Subquery(latest.values("created_at")[:1]),
    )


def _resource_collection_item(asset, *, observed_at):
    current = None
    capabilities = ["view_detail"]
    links = {
        "detail": reverse(
            "personal-projections:resource-detail",
            kwargs={"pk": asset.pk},
        )
    }
    if asset.current_version_id is not None:
        current = {
            "id": str(asset.current_version_id),
            "version": asset.current_version_number,
            "created_at": asset.current_version_created_at,
            "validity": _validity_payload(
                issued_at=asset.current_version_issued_at,
                expires_at=asset.current_version_expires_at,
                observed_at=observed_at,
            ),
        }
        capabilities.extend(["download", "reuse_in_journey"])
        links["download"] = reverse(
            "personal-projections:resource-version-download",
            kwargs={"version_id": asset.current_version_id},
        )
        links["reuse_in_journey"] = reverse(
            "personal-projections:resource-version-reuse",
            kwargs={"version_id": asset.current_version_id},
        )
    latest = None
    if current is not None:
        latest = {
            "version": current["version"],
            "issued_at": asset.current_version_issued_at,
            "expires_at": asset.current_version_expires_at,
            "created_at": current["created_at"],
        }
    return {
        "kind": "personal_asset",
        "id": str(asset.pk),
        "title": asset.title,
        "asset_kind": asset.kind,
        "asset_kind_label": asset.get_kind_display(),
        "sensitivity": asset.sensitivity,
        "sensitivity_label": asset.get_sensitivity_display(),
        "status": "active",
        "latest_version": latest,
        "current_version": current,
        "capabilities": capabilities,
        "links": links,
    }


def build_personal_resources_depth_data(
    profile,
    *,
    observed_at,
    query="",
    limit=RESOURCE_DEFAULT_LIMIT,
    offset=0,
):
    query = (query or "").strip()
    assets = personal_assets_for_controller(profile)
    if query:
        assets = assets.filter(title__icontains=query)
    assets = _current_version_annotations(assets).order_by("-updated_at", "id")

    total = assets.count()
    rows = list(assets[offset : offset + limit])
    proofs = proofs_for_profile(profile)
    credentials = credentials_for_profile(profile)
    data = {
        "documents": {
        "count": total,
        "query": query or None,
        "items": [
            _resource_collection_item(asset, observed_at=observed_at)
            for asset in rows
        ],
        "has_more": offset + len(rows) < total,
        "page": {
            "count": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + len(rows) < total,
        },
            "links": {
                "self": reverse("personal-projections:resources"),
            },
        },
        "proofs": _bounded(proofs, _proof_item, limit=RESOURCE_MAX_LIMIT),
        "credentials": _bounded(
            credentials,
            _credential_item,
            limit=RESOURCE_MAX_LIMIT,
        ),
    }
    data["invariants"] = {
        "personal_asset_is_proof": False,
        "personal_asset_satisfies_requirement_by_presence": False,
        "credential_kind": "trust_credential",
    }
    return data


def _version_payload(version, *, current, archived, observed_at):
    capabilities = []
    links = {}
    if not archived:
        capabilities.append("download")
        capabilities.append("reuse_in_journey")
        links["download"] = reverse(
            "personal-projections:resource-version-download",
            kwargs={"version_id": version.pk},
        )
        links["reuse_in_journey"] = reverse(
            "personal-projections:resource-version-reuse",
            kwargs={"version_id": version.pk},
        )
    provenance = (
        {
            "kind": "journey_artifact",
            "id": str(version.source_journey_artifact_id),
        }
        if version.source_journey_artifact_id
        else {"kind": "unknown"}
    )
    return {
        "id": str(version.pk),
        "version": version.version,
        "current": current,
        "mime_type": version.mime_type,
        "size_bytes": version.size,
        "created_at": version.created_at,
        "validity": _validity_payload(
            issued_at=version.issued_at,
            expires_at=version.expires_at,
            observed_at=observed_at,
        ),
        "provenance": provenance,
        "capabilities": capabilities,
        "links": links,
    }


def build_personal_resource_detail_data(
    profile,
    *,
    asset_id,
    observed_at,
    version_limit=RESOURCE_VERSION_DEFAULT_LIMIT,
    version_offset=0,
):
    asset = personal_asset_for_controller(
        profile,
        asset_id,
        include_archived=True,
    )
    versions = personal_asset_versions_for_controller(profile, asset).order_by(
        "-version",
        "-created_at",
    )
    version_count = versions.count()
    current = versions.first()
    page = list(versions[version_offset : version_offset + version_limit])
    archived = asset.archived_at is not None

    capabilities = ["view_detail"]
    links = {
        "self": reverse(
            "personal-projections:resource-detail",
            kwargs={"pk": asset.pk},
        ),
        "collection": reverse("personal-projections:resources"),
    }
    if not archived:
        links["web"] = reverse(
            "personal_assets:detail",
            kwargs={"asset_id": asset.pk},
        )
    if current is not None and not archived:
        capabilities.extend(["download", "reuse_in_journey"])
        links["download"] = reverse(
            "personal-projections:resource-version-download",
            kwargs={"version_id": current.pk},
        )
        links["reuse_in_journey"] = reverse(
            "personal-projections:resource-version-reuse",
            kwargs={"version_id": current.pk},
        )

    subject = {"kind": "profile", "id": str(asset.subject_profile_id)} if asset.subject_profile_id else {
        "kind": "external_beneficiary",
        "id": str(asset.subject_external_beneficiary_id),
    }

    return {
        "kind": "personal_asset",
        "id": str(asset.pk),
        "title": asset.title,
        "asset_kind": asset.kind,
        "asset_kind_label": asset.get_kind_display(),
        "sensitivity": asset.sensitivity,
        "sensitivity_label": asset.get_sensitivity_display(),
        "status": "archived" if archived else "active",
        "subject": subject,
        "created_at": asset.created_at,
        "updated_at": asset.updated_at,
        "archived_at": asset.archived_at,
        "current_version": (
            _version_payload(
                current,
                current=True,
                archived=archived,
                observed_at=observed_at,
            )
            if current is not None
            else None
        ),
        "versions": {
            "items": [
                _version_payload(
                    version,
                    current=current is not None and version.pk == current.pk,
                    archived=archived,
                    observed_at=observed_at,
                )
                for version in page
            ],
            "page": {
                "count": version_count,
                "offset": version_offset,
                "limit": version_limit,
                "has_more": version_offset + len(page) < version_count,
            },
        },
        "reuse": {
            "journey": {
                "available": bool(current is not None and not archived),
                "requires_context": ["journey_id"],
                "effect": "creates_journey_artifact_snapshot",
            }
        },
        "requirement": {
            "satisfied_by_presence": False,
            "decision_owner": "requirements_readiness",
        },
        "capabilities": capabilities,
        "links": links,
    }


def build_personal_passport_depth_data(
    profile,
    *,
    variant=PASSPORT_COMPLETE,
    topic_codes=(),
    selected_activity_ids=None,
    selected_proof_ids=None,
    selected_credential_ids=None,
    selected_sections=None,
):
    data = build_personal_passport_data(
        profile,
        variant=variant,
        topic_codes=topic_codes,
        selected_activity_ids=selected_activity_ids,
        selected_proof_ids=selected_proof_ids,
        selected_credential_ids=selected_credential_ids,
        selected_sections=selected_sections,
    )
    public_enabled = profile_has_public_passport(profile)
    variant_visibility = {
        PASSPORT_PUBLIC: "public_projection" if public_enabled else "subject_preview",
        PASSPORT_COMPLETE: "subject_private",
        PASSPORT_THEMATIC: "subject_private",
        PASSPORT_CUSTOM: "subject_private",
    }
    links = {
        "self": reverse("personal-projections:passport"),
        "presentation_web": reverse("sharing:passport-me"),
    }
    if public_enabled:
        links["public_web"] = reverse(
            "sharing:passport-profile",
            kwargs={"profile_id": profile.pk},
        )
    data["projection"] = {
        "variant": data["variant"],
        "available_variants": list(PASSPORT_VARIANTS),
        "visibility": variant_visibility[data["variant"]],
        "public_profile_enabled": public_enabled,
    }
    data["disclosure"] = {
        "declared_count": (
            len(data["declared"]["interests"]) + len(data["declared"]["open_to"])
        ),
        "established_count": len(data["established"]["proofs"]),
        "issued_count": len(data["issued"]["credentials"]),
    }
    data["capabilities"] = [
        "view",
        "select_projection",
        "present",
    ]
    data["links"] = links
    return data


def _group_owner_payload(group, profile):
    if group.space_id:
        return {
            "kind": "space",
            "id": str(group.space_id),
            "name": group.space.name,
            "slug": group.space.slug,
            "owned_by_current_profile": False,
        }
    return {
        "kind": "profile",
        "id": str(group.owner_profile_id),
        "display_name": group.owner_profile.full_name or group.owner_profile.username,
        "owned_by_current_profile": group.owner_profile_id == profile.pk,
    }


def build_personal_group_detail_data(profile, *, group_id):
    group = groups_for_profile(profile).filter(pk=group_id).first()
    if group is None:
        return None

    membership = (
        GroupMembership.objects.filter(group=group, profile=profile)
        .order_by()
        .first()
    )
    active_membership = bool(
        membership and membership.status == GroupMembershipStatus.ACTIVE
    )

    can_view_via_authority = has_group_permission(
        profile,
        PermissionCode.GROUP_VIEW,
        group,
    )
    can_manage = has_group_permission(profile, PermissionCode.GROUP_MANAGE, group)
    can_view_members = has_group_permission(
        profile,
        PermissionCode.GROUP_MEMBERS_VIEW,
        group,
    )
    can_manage_members = has_group_permission(
        profile,
        PermissionCode.GROUP_MEMBERS_MANAGE,
        group,
    )
    can_invite = has_group_permission(
        profile,
        PermissionCode.GROUP_INVITATIONS_MANAGE,
        group,
    )
    can_ownership = has_group_permission(
        profile,
        PermissionCode.GROUP_OWNERSHIP_MANAGE,
        group,
    )

    capabilities = ["view"]
    if active_membership:
        capabilities.append("leave")
    if can_manage:
        capabilities.append("edit")
    if can_view_members:
        capabilities.append("view_members")
    if can_manage_members:
        capabilities.append("manage_members")
    if can_invite:
        capabilities.append("invite")
    if can_ownership:
        capabilities.append("manage_ownership")

    links = {
        "self": reverse(
            "personal-projections:group-detail",
            kwargs={"pk": group.pk},
        ),
        "collection": reverse("personal-projections:collectives"),
        "web": reverse("groups:detail", kwargs={"slug": group.slug}),
    }
    if active_membership:
        links["leave_web"] = reverse("groups:leave", kwargs={"slug": group.slug})
    if can_manage:
        links["edit_web"] = reverse("groups:edit", kwargs={"slug": group.slug})
    if can_view_members:
        links["members_web"] = reverse(
            "groups:members",
            kwargs={"slug": group.slug},
        )
    if can_invite:
        links["invite_web"] = reverse(
            "groups:invite",
            kwargs={"slug": group.slug},
        )

    authority_actions = {
        "view": can_view_via_authority,
        "edit": can_manage,
        "view_members": can_view_members,
        "manage_members": can_manage_members,
        "invite": can_invite,
        "manage_ownership": can_ownership,
    }
    return {
        "kind": "group",
        "id": str(group.pk),
        "name": group.name,
        "slug": group.slug,
        "description": group.description or None,
        "status": group.status,
        "discoverability": group.discoverability,
        "membership_policy": group.membership_policy,
        "owner": _group_owner_payload(group, profile),
        "relationship": {
            "membership": (
                {
                    "state": membership.status,
                    "active": active_membership,
                    "joined_at": membership.joined_at,
                }
                if membership is not None
                else None
            ),
            "responsibility": None,
            "authority": {
                "authorized": any(authority_actions.values()),
                "view_authorized": can_view_via_authority,
                "management_authorized": any(
                    (
                        can_manage,
                        can_manage_members,
                        can_invite,
                        can_ownership,
                    )
                ),
            },
        },
        "members": {
            "active_count": int(getattr(group, "active_member_count", 0) or 0),
            "list_available": can_view_members,
        },
        "capabilities": capabilities,
        "links": links,
    }
