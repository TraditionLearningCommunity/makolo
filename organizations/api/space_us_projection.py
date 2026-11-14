from __future__ import annotations

import logging

from authorization.constants import PermissionCode, STANDARD_SPACE_ROLE_CODES, SystemRoleCode
from authorization.models import AuthorityScope, Role
from authorization.selectors import current_mandates, has_direct_space_permission
from organizations.models import TeamMembershipStatus

from .space_relationships_projection import build_space_relationships_projection
from .space_us_resources_projection import (
    build_space_us_resources_projection,
    can_view_space_resources,
)
from .workspace_projection import build_space_workspace


logger = logging.getLogger(__name__)

PREVIEW_LIMIT = 8


def _bounded(queryset, serializer):
    rows = list(queryset[: PREVIEW_LIMIT + 1])
    return {
        "items": [serializer(row) for row in rows[:PREVIEW_LIMIT]],
        "has_more": len(rows) > PREVIEW_LIMIT,
        "links": {},
    }


def build_space_us_projection(*, profile, space):
    workspace = build_space_workspace(profile, space)
    if workspace is None:
        return None

    direct_space = workspace["authority"]["scope"] == "space"
    can_manage_team = direct_space and has_direct_space_permission(
        profile, space, PermissionCode.SPACE_TEAM_MANAGE
    )
    can_manage_ownership = direct_space and has_direct_space_permission(
        profile, space, PermissionCode.SPACE_OWNERSHIP_MANAGE
    )

    # A display-only primary Space role: owner, then administrator, then
    # other active Space mandates. Activity-only roles do not become Space
    # authority. The complete set remains in the responsibilities depth.
    space_roles = list(
        current_mandates()
        .filter(profile=profile, scope_type=AuthorityScope.SPACE, space=space)
        .select_related("role")
        .order_by("role__name", "pk")
    )
    role_rank = {
        SystemRoleCode.SPACE_OWNER: 0,
        SystemRoleCode.SPACE_ADMIN: 1,
    }
    space_roles.sort(key=lambda mandate: (
        role_rank.get(mandate.role.code, 2),
        mandate.role.name,
        mandate.pk,
    ))
    primary_role = (
        {"code": space_roles[0].role.code, "label": space_roles[0].role.name}
        if space_roles else None
    )

    # Team counts are private unless the viewer can manage the team.
    team = {
        "active_members": None,
        "visibility": "restricted",
        "role_options": [],
        "items": [],
        "has_more": False,
        "links": {},
    }
    if can_manage_team:
        team["visibility"] = "visible"
        allowed_role_codes = set(STANDARD_SPACE_ROLE_CODES)
        if not can_manage_ownership:
            allowed_role_codes.discard(SystemRoleCode.SPACE_OWNER)
        team["role_options"] = [
            {"code": role.code, "label": role.name}
            for role in Role.objects.filter(
                scope_type=AuthorityScope.SPACE,
                is_system=True,
                is_active=True,
                code__in=allowed_role_codes,
            ).order_by("name", "code")
        ]
        memberships = (
            space.teams.filter(is_default=True, memberships__status=TeamMembershipStatus.ACTIVE)
            .values("memberships__id", "memberships__user_id", "memberships__user__first_name", "memberships__user__last_name", "memberships__user__username")
            .order_by("memberships__user__first_name", "memberships__user__last_name", "memberships__id")
        )
        team.update(
            _bounded(
                memberships,
                lambda row: {
                    "kind": "team_member",
                    "id": str(row["memberships__id"]),
                    "profile": {
                        "id": str(row["memberships__user_id"]),
                        "name": (
                            f'{row["memberships__user__first_name"]} {row["memberships__user__last_name"]}'.strip()
                            or row["memberships__user__username"]
                        ),
                    },
                },
            )
        )
        team["active_members"] = workspace.get("team_summary", {}).get("active_members", 0)
        team["links"] = {"team": f"/api/v1/organizations/workspaces/{space.slug}/team/"}

    owners = {"items": [], "has_more": False, "links": {}, "visibility": "restricted"}
    if can_manage_ownership:
        mandates = (
            current_mandates()
            .filter(
                scope_type=AuthorityScope.SPACE,
                space=space,
                role__is_system=True,
                role__code=SystemRoleCode.SPACE_OWNER,
            )
            .select_related("profile")
            .order_by("profile__first_name", "profile__last_name", "pk")
        )
        owners = _bounded(
            mandates,
            lambda mandate: {
                "kind": "owner_mandate",
                "id": str(mandate.pk),
                "profile": {
                    "id": str(mandate.profile_id),
                    "name": mandate.profile.full_name or mandate.profile.username,
                },
                "responsibility": {"label": mandate.role.name},
                "authority_scope": {"kind": "space"},
            },
        )
        owners["visibility"] = "visible"
        owners["links"] = {
            "transfer": f"/api/v1/organizations/workspaces/{space.slug}/ownership/transfer/"
        }

    # Compose only the relation owner's already-authorized projection.  Nous
    # presents these facts; it does not grant access to their owning domains.
    relations = build_space_relationships_projection(profile=profile, space=space)
    relation_sections = (relations or {}).get("sections", {})
    relationships = {
        "label": (relations or {}).get("label", "Personnes & relations"),
        "sections": {
            key: {
                "items": value.get("items", [])[:4],
                "has_more": value.get("has_more", False) or len(value.get("items", [])) > 4,
            }
            for key, value in relation_sections.items()
        },
        "visibility": "visible" if relation_sections else "restricted",
    }

    modules = {row["key"]: row for row in workspace.get("modules", [])}
    institutional_links = {
        "workspace": workspace["links"]["workspace"],
    }
    if "trust" in modules:
        institutional_links["trust"] = modules["trust"]["links"].get("summary")
    if "interoperability" in modules:
        institutional_links["interoperability"] = modules["interoperability"]["links"]

    space_data = workspace["space"]
    identity = {
        "id": space_data["id"],
        "slug": space_data["slug"],
        "name": space_data["name"],
        "description": space_data.get("description"),
        "archetype": space_data["archetype"],
        "lifecycle": space_data["lifecycle"],
        "public_profile": space_data.get("public_profile"),
    }
    if direct_space:
        identity.update(
            {
                "website": space.website or None,
                "contact_email": space.contact_email or None,
                "contact_phone": space.contact_phone or None,
                "searchable": bool(space.searchable),
                "location": {
                    "country": space.country or None,
                    "city": space.city or None,
                },
            }
        )

    handoffs = {
        "responsibilities": f"/space/{space.slug}/us/responsibilities",
        "authority": f"/space/{space.slug}/us/authority",
    }
    if relation_sections:
        handoffs["relationships"] = f"/space/{space.slug}/us/relationships"
    if can_manage_team:
        handoffs["team"] = f"/space/{space.slug}/us/team"
    if can_manage_ownership:
        handoffs["ownership"] = f"/space/{space.slug}/us/ownership"
    if "trust" in modules:
        handoffs["trust"] = f"/space/{space.slug}/us/trust"
    if any(row["key"] == "analytics" for row in workspace.get("modules", [])):
        handoffs["pilot"] = f"/space/{space.slug}/us/pilot"
    if workspace["capabilities"].get("update_space"):
        handoffs["settings"] = f"/space/{space.slug}/us/settings"
        # Only an actual SPACE_MANAGE authorization opens collective issuance.
        handoffs["passport"] = f"/space/{space.slug}/us/passport"
    resources = {"visibility": "restricted", "items": [], "count": None, "counts": {}}
    if can_view_space_resources(profile=profile, space=space):
        try:
            resources = build_space_us_resources_projection(
                profile=profile, space=space, preview=True,
            )
        except Exception:
            # The optional owner read model may fail independently. Never
            # erase Space identity or pretend that an unavailable list is empty.
            logger.exception("Space Nous Resources owner projection failed")
            resources = {
                "visibility": "unavailable", "items": [],
                "count": None, "counts": {},
            }
        else:
            handoffs["resources"] = f"/space/{space.slug}/us/resources"
    if has_direct_space_permission(profile, space, PermissionCode.SPACE_MANAGE):
        handoffs["connections"] = f"/space/{space.slug}/connections"
    can_view_subscription = direct_space and (
        has_direct_space_permission(profile, space, PermissionCode.SPACE_SUBSCRIPTION_VIEW)
        or has_direct_space_permission(profile, space, PermissionCode.SPACE_SUBSCRIPTION_MANAGE)
    )
    if can_view_subscription:
        handoffs["subscription"] = f"/space/{space.slug}/subscription"

    return {
        "identity": identity,
        "team": team,
        "primary_role": primary_role,
        "responsibilities": {
            "items": workspace.get("responsibilities", []),
            "links": {},
        },
        "ownership": owners,
        "relationships": relationships,
        "resources": resources,
        "trust": workspace.get("verification", {"verified": False, "claims": []}),
        "organization": {
            "operating_preset": workspace.get("operating_preset", {}),
            "operational_footprint": workspace.get("operational_footprint"),
        },
        "authority": workspace["authority"],
        "links": institutional_links,
        "handoffs": handoffs,
        "capabilities": {
            "update_space": workspace["capabilities"].get("update_space", False),
            "manage_team": can_manage_team,
            "manage_ownership": can_manage_ownership,
        },
    }
