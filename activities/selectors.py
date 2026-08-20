from django.utils import timezone

from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission

from .models import Activity, Occurrence, OccurrencePlaceRole


def activities_for_space(space):
    return Activity.objects.filter(space=space).select_related("space", "created_by")


def manageable_activities(profile):
    queryset = Activity.objects.select_related("space", "created_by")
    ids = activity_ids_with_permission(profile, PermissionCode.ACTIVITY_MANAGE)
    if ids is None:
        return queryset
    return queryset.filter(pk__in=ids)


def occurrences_for_activity(activity):
    return Occurrence.objects.filter(activity=activity).prefetch_related("place_links__place")


def future_occurrences(*, at=None):
    return Occurrence.objects.filter(start_at__gt=at or timezone.now()).select_related("activity", "activity__space")


def occurrence_with_places(pk):
    return (
        Occurrence.objects.select_related("activity", "activity__space")
        .prefetch_related("place_links__place")
        .get(pk=pk)
    )


def primary_place_for_occurrence(occurrence):
    """Return the canonical primary Place for one Occurrence, if any."""
    cached = getattr(occurrence, "_prefetched_objects_cache", {}).get("place_links")
    if cached is not None:
        link = next((row for row in cached if row.role == OccurrencePlaceRole.PRIMARY), None)
        return link.place if link else None
    link = (
        occurrence.place_links.select_related("place")
        .filter(role=OccurrencePlaceRole.PRIMARY)
        .order_by("position", "id")
        .first()
    )
    return link.place if link else None
