from __future__ import annotations

from authorization.constants import PermissionCode
from authorization.selectors import has_direct_space_permission
from crm.canonical_models import Audience, AudienceStatus
from crm.selectors import get_contacts_visible_to
from groups.models import GroupStatus
from organizations.models import TeamMembershipStatus
from organizations.space_product import relationships_label_for_space
from partners.selectors import get_partners_visible_to

from .workspace_projection import build_space_workspace


PREVIEW_LIMIT = 12


def _collection(queryset, serializer, *, links=None):
    rows = list(queryset[: PREVIEW_LIMIT + 1])
    return {
        "items": [serializer(row) for row in rows[:PREVIEW_LIMIT]],
        "has_more": len(rows) > PREVIEW_LIMIT,
        "links": links or {},
    }


def _empty(*, links=None):
    return {"items": [], "has_more": False, "links": links or {}}


def build_space_relationships_projection(*, profile, space):
    workspace = build_space_workspace(profile, space)
    if workspace is None:
        return None

    direct_space = workspace["authority"]["scope"] == "space"
    sections = {}

    if direct_space and has_direct_space_permission(
        profile, space, PermissionCode.SPACE_TEAM_MANAGE
    ):
        memberships = (
            space.teams.filter(
                is_default=True,
                memberships__status=TeamMembershipStatus.ACTIVE,
            )
            .values(
                "memberships__id",
                "memberships__user_id",
                "memberships__user__first_name",
                "memberships__user__last_name",
                "memberships__user__username",
            )
            .order_by("memberships__user__first_name", "memberships__user__last_name", "memberships__id")
        )
        sections["team"] = _collection(
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
            links={"deep": f"/api/v1/organizations/workspaces/{space.slug}/team/"},
        )

    if direct_space and (
        has_direct_space_permission(profile, space, PermissionCode.SPACE_GROUPS_VIEW)
        or has_direct_space_permission(profile, space, PermissionCode.SPACE_GROUPS_MANAGE)
    ):
        groups = space.collective_groups.filter(status=GroupStatus.ACTIVE).order_by("name", "pk")
        sections["groups"] = _collection(
            groups,
            lambda group: {
                "kind": "group",
                "id": str(group.pk),
                "name": group.name,
                "status": group.status,
                "links": {"detail": f"/groups/{group.slug}/"},
            },
            links={"deep": "/groups/"},
        )

    crm_visible = direct_space and has_direct_space_permission(
        profile, space, PermissionCode.CRM_VIEW
    )
    if crm_visible:
        contacts = (
            get_contacts_visible_to(profile)
            .filter(organization=space)
            .select_related("user")
            .order_by("name", "pk")
        )
        sections["crm_contacts"] = _collection(
            contacts,
            lambda contact: {
                "kind": "crm_contact",
                "id": str(contact.pk),
                "profile": (
                    {
                        "id": str(contact.user_id),
                        "name": contact.user.full_name or contact.user.username,
                    }
                    if contact.user_id
                    else None
                ),
                "label": contact.name or "Contact CRM",
                "source": contact.source,
            },
            links={"deep": f"/api/v1/crm/contacts/?organization={space.pk}"},
        )
        audiences = Audience.objects.filter(
            organization=space, status=AudienceStatus.ACTIVE
        ).order_by("name", "pk")
        sections["audiences"] = _collection(
            audiences,
            lambda audience: {
                "kind": "audience",
                "id": str(audience.pk),
                "name": audience.name,
                "status": audience.status,
            },
        )

    partner_visible = direct_space and (
        has_direct_space_permission(profile, space, PermissionCode.PARTNERS_MANAGE)
        or has_direct_space_permission(profile, space, PermissionCode.PARTNERS_FINANCE)
    )
    if partner_visible:
        partners = (
            get_partners_visible_to(profile)
            .filter(organization=space)
            .select_related("user")
            .order_by("name", "pk")
        )
        sections["partners"] = _collection(
            partners,
            lambda partner: {
                "kind": "partner",
                "id": str(partner.pk),
                "name": partner.display_name,
                "partner_kind": partner.kind,
                "status": partner.status,
                "profile": (
                    {
                        "id": str(partner.user_id),
                        "name": partner.user.full_name or partner.user.username,
                    }
                    if partner.user_id
                    else None
                ),
            },
            links={"deep": f"/api/v1/partners/partners/?organization={space.pk}"},
        )

    return {
        "label": relationships_label_for_space(space),
        "authority": workspace["authority"],
        "sections": sections,
        "links": {"workspace": workspace["links"]["workspace"]},
        "capabilities": {
            "manage_team": workspace["capabilities"].get("manage_team", False),
            "manage_groups": direct_space
            and has_direct_space_permission(profile, space, PermissionCode.SPACE_GROUPS_MANAGE),
            "manage_crm": direct_space
            and has_direct_space_permission(profile, space, PermissionCode.CRM_MANAGE),
            "manage_partners": direct_space
            and has_direct_space_permission(profile, space, PermissionCode.PARTNERS_MANAGE),
        },
    }
