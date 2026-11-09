"""Shared, explicit provenance for the demo generation toolchain.

The prefix is internal: it does not change public titles or owner authority.
Only synthetic Activities and synthetic-owned Spaces are eligible for upkeep.
"""
from django.db.models import Q

DEMO_ACTIVITY_PREFIX = "demo-"
DEMO_PROFILE_PREFIX = "world_"


def demo_activities(queryset):
    """Restrict Activity querysets to the generator's synthetic namespace."""
    return queryset.filter(slug__startswith=DEMO_ACTIVITY_PREFIX)


def demo_spaces(queryset, people):
    """Spaces created by demo profiles using the existing ecosystem naming."""
    from .editorial import space_name

    names = [space_name(profile) for profile in people]
    return queryset.filter(
        created_by__in=people
    ).filter(
        Q(name__in=names)
        | Q(name__startswith="[DEMO] Espace ")
        | Q(name__startswith="Espace world_")
    )


def synthetic_owner(activity):
    """Guard mutable synthetic records without changing their ownership."""
    if not str(activity.slug).startswith(DEMO_ACTIVITY_PREFIX):
        return False
    owner = activity.owner_profile or (
        activity.space.created_by if activity.space_id else None
    )
    return bool(
        owner and owner.is_active
        and owner.username.startswith(DEMO_PROFILE_PREFIX)
        and not owner.is_staff and not owner.is_superuser
    )
