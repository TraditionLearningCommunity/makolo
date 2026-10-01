from __future__ import annotations

from authorization.constants import PermissionCode, SystemRoleCode
from authorization.models import AuthorityScope
from authorization.selectors import current_mandates, has_direct_space_permission
from organizations.models import TeamMembershipStatus

from .workspace_projection import build_space_workspace


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

    team = {
        "active_members": workspace.get("team_summary", {}).get("active_members"),
        "items": [],
        "has_more": False,
        "links": {},
    }
    if can_manage_team:
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

    owners = {"items": [], "has_more": False, "links": {}}
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
        owners["links"] = {
            "transfer": f"/api/v1/organizations/workspaces/{space.slug}/ownership/transfer/"
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
                "location": {
                    "country": space.country or None,
                    "city": space.city or None,
                },
            }
        )

    return {
        "identity": identity,
        "team": team,
        "responsibilities": {
            "items": workspace.get("responsibilities", []),
            "links": {},
        },
        "ownership": owners,
        "trust": workspace.get("verification", {"verified": False, "claims": []}),
        "organization": {
            "operating_preset": workspace.get("operating_preset", {}),
            "operational_footprint": workspace.get("operational_footprint"),
        },
        "authority": workspace["authority"],
        "links": institutional_links,
        "capabilities": {
            "update_space": workspace["capabilities"].get("update_space", False),
            "manage_team": can_manage_team,
            "manage_ownership": can_manage_ownership,
        },
    }
