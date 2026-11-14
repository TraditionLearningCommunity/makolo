"""N3 Nous: private read-only authority drawn from canonical Mandates."""
from __future__ import annotations

from collections import defaultdict

from django.db.models import Q

from authorization.models import AuthorityScope, RolePermission
from authorization.selectors import current_mandates


def build_space_us_authority(*, profile, space):
    """Expose only the viewer's effective Space/Activity roles in this Space."""
    if not getattr(profile, "is_authenticated", False):
        return None
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

    permissions_by_role = defaultdict(list)
    for link in (
        RolePermission.objects.filter(
            role_id__in={mandate.role_id for mandate in mandates},
            permission__is_active=True,
        )
        .select_related("permission")
        .order_by("permission__name", "permission__code")
    ):
        permissions_by_role[link.role_id].append(
            {"code": link.permission.code, "label": link.permission.name}
        )

    rows = []
    for mandate in mandates:
        is_space = mandate.scope_type == AuthorityScope.SPACE
        rows.append(
            {
                "key": f"mandate:{mandate.pk}",
                "role": {
                    "code": mandate.role.code,
                    "label": mandate.role.name,
                    "description": mandate.role.description,
                },
                "scope": {
                    "kind": mandate.scope_type,
                    "label": "Espace" if is_space else "Activité",
                    "target": space.name if is_space else mandate.activity.title,
                },
                "valid_from": mandate.valid_from,
                "valid_until": mandate.valid_until,
                "permissions": permissions_by_role[mandate.role_id],
            }
        )
    return {"space_id": str(space.pk), "space_name": space.name, "mandates": rows}
