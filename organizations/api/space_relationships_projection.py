from __future__ import annotations

from django.core.exceptions import ValidationError
from django.db.models import Q

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
SEARCH_LIMIT = 50


def _collection(queryset, serializer, *, links=None):
    rows = list(queryset[: PREVIEW_LIMIT + 1])
    return {
        "items": [serializer(row) for row in rows[:PREVIEW_LIMIT]],
        "has_more": len(rows) > PREVIEW_LIMIT,
        "links": links or {},
    }


def _team_rows(space, query=None, membership_id=None):
    predicates = Q(
        is_default=True,
        memberships__status=TeamMembershipStatus.ACTIVE,
    )
    if query:
        predicates &= (
            Q(memberships__user__first_name__icontains=query)
            | Q(memberships__user__last_name__icontains=query)
            | Q(memberships__user__username__icontains=query)
        )
    if membership_id:
        predicates &= Q(memberships__id=membership_id)
    rows = space.teams.filter(predicates)
    return (
        rows.values(
            "name",
            "memberships__id",
            "memberships__user_id",
            "memberships__user__first_name",
            "memberships__user__last_name",
            "memberships__user__username",
        )
        .order_by(
            "memberships__user__first_name",
            "memberships__user__last_name",
            "memberships__id",
        )
    )


def _team_item(row, *, space, can_manage):
    profile_name = (
        f'{row["memberships__user__first_name"]} '
        f'{row["memberships__user__last_name"]}'
    ).strip() or row["memberships__user__username"]
    return {
        "kind": "team_member",
        "id": str(row["memberships__id"]),
        "profile": {
            "id": str(row["memberships__user_id"]),
            "name": profile_name,
        },
        "relation_type": "Collaborateur · Équipe",
        "owner": "team",
        "owner_identity": row["name"] or "Équipe principale",
        "capabilities": {"manage": can_manage},
        "links": {
            "owner_api": f"/api/v1/organizations/workspaces/{space.slug}/team/",
        },
    }


def _group_item(group, *, space, can_manage):
    return {
        "kind": "group",
        "id": str(group.pk),
        "name": group.name,
        "status": group.status,
        "relation_type": "Groupe",
        "owner": "groups",
        "owner_identity": group.name,
        "profile": None,
        "capabilities": {"manage": can_manage},
        "links": {
            "owner_web": f"/spaces/{space.slug}/groups/",
        },
    }


def _contact_item(contact, *, space, can_manage):
    profile = (
        {
            "id": str(contact.user_id),
            "name": contact.user.full_name or contact.user.username,
        }
        if contact.user_id
        else None
    )
    return {
        "kind": "crm_contact",
        "id": str(contact.pk),
        "profile": profile,
        "label": contact.name or "Contact",
        "source": contact.source,
        "relation_type": "Contact CRM",
        "owner": "crm",
        "owner_identity": contact.name or "Contact CRM",
        "capabilities": {"manage": can_manage},
        "links": {
            "owner_api": f"/api/v1/crm/contacts/?organization={space.pk}",
            "owner_web": f"/spaces/{space.slug}/crm/",
        },
    }


def _audience_item(audience, *, space, can_manage):
    return {
        "kind": "audience",
        "id": str(audience.pk),
        "name": audience.name,
        "status": audience.status,
        "relation_type": "Audience",
        "owner": "audiences",
        "owner_identity": audience.name,
        "profile": None,
        "capabilities": {"manage": can_manage},
        "links": {
            "owner_web": f"/spaces/{space.slug}/audiences/",
        },
    }


def _partner_item(partner, *, space, can_manage):
    profile = (
        {
            "id": str(partner.user_id),
            "name": partner.user.full_name or partner.user.username,
        }
        if partner.user_id
        else None
    )
    relation_type = "Partenaire"
    if partner.kind:
        relation_type = f"Partenaire · {partner.kind}"
    return {
        "kind": "partner",
        "id": str(partner.pk),
        "name": partner.display_name,
        "partner_kind": partner.kind,
        "status": partner.status,
        "profile": profile,
        "relation_type": relation_type,
        "owner": "partners",
        "owner_identity": partner.display_name,
        "capabilities": {"manage": can_manage},
        "links": {
            "owner_api": f"/api/v1/partners/partners/?organization={space.pk}",
            "owner_web": f"/spaces/{space.slug}/partners/",
        },
    }


def _identity(item):
    profile = item.get("profile")
    if profile:
        return profile.get("name") or item.get("name") or item.get("label") or ""
    return item.get("name") or item.get("label") or item.get("owner_identity") or ""


def _search_item(item):
    return {
        "kind": item["kind"],
        "id": item["id"],
        "identity": _identity(item),
        "relation_type": item["relation_type"],
        "owner": item["owner"],
        "owner_identity": item["owner_identity"],
        "profile": item.get("profile"),
        "capabilities": item.get("capabilities", {}),
        "links": item.get("links", {}),
    }


def _safe_first(queryset, **filters):
    try:
        return queryset.filter(**filters).first()
    except (ValueError, ValidationError):
        return None


def _build_search(
    *,
    query,
    team_visible,
    group_visible,
    crm_visible,
    partner_visible,
    team_rows,
    groups,
    contacts,
    audiences,
    partners,
    serializers,
):
    if not query:
        return None

    candidates = []
    if team_visible:
        candidates.extend(
            _search_item(serializers["team"](row))
            for row in team_rows(query=query)[: SEARCH_LIMIT + 1]
        )
    if group_visible:
        candidates.extend(
            _search_item(serializers["groups"](row))
            for row in groups.filter(name__icontains=query)[: SEARCH_LIMIT + 1]
        )
    if crm_visible:
        contact_query = (
            Q(name__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__username__icontains=query)
        )
        candidates.extend(
            _search_item(serializers["crm_contacts"](row))
            for row in contacts.filter(contact_query)[: SEARCH_LIMIT + 1]
        )
        candidates.extend(
            _search_item(serializers["audiences"](row))
            for row in audiences.filter(name__icontains=query)[: SEARCH_LIMIT + 1]
        )
    if partner_visible:
        partner_query = (
            Q(name__icontains=query)
            | Q(user__first_name__icontains=query)
            | Q(user__last_name__icontains=query)
            | Q(user__username__icontains=query)
        )
        candidates.extend(
            _search_item(serializers["partners"](row))
            for row in partners.filter(partner_query)[: SEARCH_LIMIT + 1]
        )

    candidates.sort(key=lambda item: (item["identity"].casefold(), item["owner"], item["id"]))
    has_more = len(candidates) > SEARCH_LIMIT
    items = candidates[:SEARCH_LIMIT]
    return {
        "query": query,
        "state": "results" if items else "no_match",
        "items": items,
        "has_more": has_more,
        "scope": "visible_space_relationships",
    }


def _build_selection(
    *,
    relation_kind,
    relation_id,
    team_visible,
    group_visible,
    crm_visible,
    partner_visible,
    team_rows,
    groups,
    contacts,
    audiences,
    partners,
    serializers,
):
    if not relation_kind or not relation_id:
        return None

    if relation_kind == "team_member" and team_visible:
        row = team_rows(membership_id=relation_id).first()
        return serializers["team"](row) if row else None
    if relation_kind == "group" and group_visible:
        row = _safe_first(groups, pk=relation_id)
        return serializers["groups"](row) if row else None
    if relation_kind == "crm_contact" and crm_visible:
        row = _safe_first(contacts, pk=relation_id)
        return serializers["crm_contacts"](row) if row else None
    if relation_kind == "audience" and crm_visible:
        row = _safe_first(audiences, pk=relation_id)
        return serializers["audiences"](row) if row else None
    if relation_kind == "partner" and partner_visible:
        row = _safe_first(partners, pk=relation_id)
        return serializers["partners"](row) if row else None
    return None


def build_space_relationships_projection(
    *,
    profile,
    space,
    query=None,
    relation_kind=None,
    relation_id=None,
):
    workspace = build_space_workspace(profile, space)
    if workspace is None:
        return None

    direct_space = workspace["authority"]["scope"] == "space"
    team_visible = direct_space and has_direct_space_permission(
        profile, space, PermissionCode.SPACE_TEAM_MANAGE
    )
    group_visible = direct_space and (
        has_direct_space_permission(profile, space, PermissionCode.SPACE_GROUPS_VIEW)
        or has_direct_space_permission(profile, space, PermissionCode.SPACE_GROUPS_MANAGE)
    )
    crm_visible = direct_space and has_direct_space_permission(
        profile, space, PermissionCode.CRM_VIEW
    )
    partner_visible = direct_space and (
        has_direct_space_permission(profile, space, PermissionCode.PARTNERS_MANAGE)
        or has_direct_space_permission(profile, space, PermissionCode.PARTNERS_FINANCE)
    )

    can_manage_team = workspace["capabilities"].get("manage_team", False)
    can_manage_groups = direct_space and has_direct_space_permission(
        profile, space, PermissionCode.SPACE_GROUPS_MANAGE
    )
    can_manage_crm = direct_space and has_direct_space_permission(
        profile, space, PermissionCode.CRM_MANAGE
    )
    can_manage_partners = direct_space and has_direct_space_permission(
        profile, space, PermissionCode.PARTNERS_MANAGE
    )

    groups = space.collective_groups.filter(status=GroupStatus.ACTIVE).order_by("name", "pk")
    contacts = (
        get_contacts_visible_to(profile)
        .filter(organization=space)
        .select_related("user")
        .order_by("name", "pk")
    )
    audiences = Audience.objects.filter(
        organization=space, status=AudienceStatus.ACTIVE
    ).order_by("name", "pk")
    partners = (
        get_partners_visible_to(profile)
        .filter(organization=space)
        .select_related("user")
        .order_by("name", "pk")
    )

    serializers = {
        "team": lambda row: _team_item(row, space=space, can_manage=can_manage_team),
        "groups": lambda row: _group_item(row, space=space, can_manage=can_manage_groups),
        "crm_contacts": lambda row: _contact_item(row, space=space, can_manage=can_manage_crm),
        "audiences": lambda row: _audience_item(row, space=space, can_manage=can_manage_crm),
        "partners": lambda row: _partner_item(row, space=space, can_manage=can_manage_partners),
    }

    sections = {}
    if team_visible:
        sections["team"] = _collection(
            _team_rows(space),
            serializers["team"],
            links={"deep": f"/api/v1/organizations/workspaces/{space.slug}/team/"},
        )
    if group_visible:
        sections["groups"] = _collection(groups, serializers["groups"])
    if crm_visible:
        sections["crm_contacts"] = _collection(
            contacts,
            serializers["crm_contacts"],
            links={"deep": f"/api/v1/crm/contacts/?organization={space.pk}"},
        )
        sections["audiences"] = _collection(audiences, serializers["audiences"])
    if partner_visible:
        sections["partners"] = _collection(
            partners,
            serializers["partners"],
            links={"deep": f"/api/v1/partners/partners/?organization={space.pk}"},
        )

    normalized_query = (query or "").strip()
    search = _build_search(
        query=normalized_query,
        team_visible=team_visible,
        group_visible=group_visible,
        crm_visible=crm_visible,
        partner_visible=partner_visible,
        team_rows=lambda query=None, membership_id=None: _team_rows(
            space, query=query, membership_id=membership_id
        ),
        groups=groups,
        contacts=contacts,
        audiences=audiences,
        partners=partners,
        serializers=serializers,
    )
    selection = _build_selection(
        relation_kind=(relation_kind or "").strip(),
        relation_id=(relation_id or "").strip(),
        team_visible=team_visible,
        group_visible=group_visible,
        crm_visible=crm_visible,
        partner_visible=partner_visible,
        team_rows=lambda membership_id=None: _team_rows(
            space, membership_id=membership_id
        ),
        groups=groups,
        contacts=contacts,
        audiences=audiences,
        partners=partners,
        serializers=serializers,
    )

    return {
        "label": relationships_label_for_space(space),
        "authority": workspace["authority"],
        "sections": sections,
        "search": search,
        "selection": selection,
        "links": {"workspace": workspace["links"]["workspace"]},
        "capabilities": {
            "manage_team": can_manage_team,
            "manage_groups": can_manage_groups,
            "manage_crm": can_manage_crm,
            "manage_partners": can_manage_partners,
        },
    }
