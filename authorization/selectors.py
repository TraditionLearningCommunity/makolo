"""Read-side helpers for effective Makolo authority."""

from __future__ import annotations

from .models import AuthorityScope, Mandate
from .services import ACTIVITY_PERMISSION_INHERITANCE, _current_mandate_q


def current_mandates(*, at=None):
    """Return Mandates that are effective at ``at`` using the runtime resolver rule.

    Keeping this selector backed by the resolver's canonical predicate prevents
    product surfaces from drifting from ``can()`` on status or validity windows.
    Callers can further constrain the returned queryset by scope and target.
    """

    return Mandate.objects.filter(_current_mandate_q(at), role__is_active=True)



def space_ids_with_direct_permission(profile, permission_code: str, *, at=None):
    """Return Space ids authorized by Space-scoped Mandates only.

    Unlike the general authorization resolver, this selector deliberately does
    not inherit Platform authority. It is intended for contracts where acting
    *as an Espace* must remain distinct from Platform supervision.
    """
    if not getattr(profile, "is_authenticated", False):
        return []
    return list(
        current_mandates(at=at)
        .filter(
            profile=profile,
            scope_type=AuthorityScope.SPACE,
            role__role_permissions__permission__code=permission_code,
            role__role_permissions__permission__is_active=True,
        )
        .exclude(space_id=None)
        .values_list("space_id", flat=True)
        .distinct()
    )


def has_direct_space_permission(profile, space, permission_code: str, *, at=None) -> bool:
    if not getattr(profile, "is_authenticated", False):
        return False
    return (
        current_mandates(at=at)
        .filter(
            profile=profile,
            scope_type=AuthorityScope.SPACE,
            space=space,
            role__role_permissions__permission__code=permission_code,
            role__role_permissions__permission__is_active=True,
        )
        .exists()
    )


def activity_ids_with_direct_permission(profile, permission_code: str, *, at=None):
    """Return Activity ids from Activity Mandates plus explicit Space inheritance.

    Platform Mandates are intentionally excluded. Space inheritance follows the
    same mapping as the canonical resolver, but only from real Space Mandates.
    """
    if not getattr(profile, "is_authenticated", False):
        return []

    ids = set(
        current_mandates(at=at)
        .filter(
            profile=profile,
            scope_type=AuthorityScope.ACTIVITY,
            role__role_permissions__permission__code=permission_code,
            role__role_permissions__permission__is_active=True,
        )
        .exclude(activity_id=None)
        .values_list("activity_id", flat=True)
    )
    inherited = ACTIVITY_PERMISSION_INHERITANCE.get(permission_code)
    if inherited:
        space_ids = space_ids_with_direct_permission(
            profile,
            inherited,
            at=at,
        )
        if space_ids:
            from activities.models import Activity

            ids.update(
                Activity.objects.filter(space_id__in=space_ids).values_list(
                    "pk",
                    flat=True,
                )
            )
    return list(ids)


def has_direct_activity_permission(profile, activity, permission_code: str, *, at=None) -> bool:
    return activity.pk in set(
        activity_ids_with_direct_permission(
            profile,
            permission_code,
            at=at,
        )
    )
