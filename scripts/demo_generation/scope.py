"""Shared, explicit provenance for the demo generation toolchain.

The prefix is internal: it does not change public titles or owner authority.
Only synthetic Activities and synthetic-owned Spaces are eligible for upkeep.
"""
DEMO_ACTIVITY_PREFIX = "demo-"
DEMO_PROFILE_PREFIX = "world_"


def demo_activities(queryset):
    """Restrict Activity querysets to the generator's synthetic namespace."""
    return queryset.filter(slug__startswith=DEMO_ACTIVITY_PREFIX)


def demo_spaces(queryset, people):
    """Spaces created by demo profiles using the existing ecosystem naming."""
    from django.db.models import Q
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


def backup_demo_sqlite(connection):
    """Online SQLite backup, explicitly requested before an upkeep write."""
    import sqlite3
    from datetime import datetime, timezone
    from pathlib import Path

    if connection.vendor != "sqlite":
        raise ValueError("Demo backup requires SQLite")
    source = Path(str(connection.settings_dict["NAME"])).resolve()
    if not source.is_file():
        raise ValueError("SQLite source file not found")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    destination = source.with_name(source.name + ".demo-backup-" + stamp)
    with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
        src.backup(dst)
    return destination


def synthetic_journey_activity_prefixes(profile):
    """Return proven demo Activity namespaces belonging to the selected owner.

    A named synthetic Mobile Mature persona uses mobile-mature- Activities.
    The normal world_* generator keeps its original demo- scope. Never infer
    demo provenance just because a username was explicitly supplied.
    """
    metadata = getattr(profile, "metadata", None)
    if (
        isinstance(metadata, dict)
        and metadata.get("seed") == "mobile-mature-universe"
    ):
        return ("demo-", "mobile-mature-")
    if str(getattr(profile, "username", "")).startswith(DEMO_PROFILE_PREFIX):
        return (DEMO_ACTIVITY_PREFIX,)
    return ()
