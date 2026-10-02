from __future__ import annotations

from django.db.models import Q

from authorization.models import AuthorityScope
from authorization.selectors import current_mandates
from organizations.space_product import operating_preset_for_space


def _space_context(*, profile, space, responsibility_key=None):
    mandates = list(
        current_mandates()
        .filter(profile=profile)
        .filter(
            Q(scope_type=AuthorityScope.SPACE, space=space)
            | Q(scope_type=AuthorityScope.ACTIVITY, activity__space=space)
        )
        .select_related("role", "activity")
        .order_by("scope_type", "role__name", "activity__title", "pk")
    )
    if not mandates:
        return None

    responsibility = responsibility_key or "all"
    if responsibility != "all":
        prefix = "mandate:"
        if not responsibility.startswith(prefix):
            return None
        mandate_id = responsibility[len(prefix) :]
        if not any(str(mandate.pk) == mandate_id for mandate in mandates):
            return None

    direct_space_authority = any(
        mandate.scope_type == AuthorityScope.SPACE for mandate in mandates
    )
    preset = operating_preset_for_space(space)
    return {
        "space": {
            "id": str(space.pk),
            "slug": space.slug,
            "name": space.name,
        },
        "archetype": space.archetype,
        "primary_business_label": preset.primary_business_label,
        "authority": {
            "scope": "space" if direct_space_authority else "activity_limited",
            "limited_to_activities": not direct_space_authority,
        },
        "responsibility": responsibility,
    }


def _links(space):
    base = f"/api/v1/organizations/workspaces/{space.slug}"
    return {
        "workspace": f"{base}/",
        "now": f"{base}/now/",
        "discover": f"{base}/discover/",
        "work": f"{base}/work/",
        "us": f"{base}/us/",
        "relationships": f"{base}/relationships/",
        "pilot": f"{base}/pilot/",
        "mark": f"{base}/mark/",
    }


def build_space_now_projection(*, profile, space, responsibility_key=None):
    context = _space_context(
        profile=profile,
        space=space,
        responsibility_key=responsibility_key,
    )
    if context is None:
        return None
    return {
        **context,
        "selection": {
            "state": "unavailable",
            "reason": "no_safe_selection_contract",
        },
        "items": [],
        "has_more": False,
        "links": _links(space),
        "capabilities": {},
    }


def build_space_discover_projection(*, profile, space):
    context = _space_context(profile=profile, space=space)
    if context is None:
        return None
    return {
        **context,
        "selection": {
            "state": "unavailable",
            "reason": "no_safe_selection_contract",
        },
        "items": [],
        "has_more": False,
        "links": _links(space),
        "capabilities": {},
    }
