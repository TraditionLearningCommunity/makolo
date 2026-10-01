from __future__ import annotations

from django.db.models import Q
from django.utils import timezone

from activities.models import Activity, ActivityStatus, Occurrence, OccurrenceStatus
from authorization.constants import PermissionCode
from authorization.models import AuthorityScope
from authorization.selectors import (
    activity_ids_with_direct_permission,
    current_mandates,
    has_direct_space_permission,
)
from organizations.space_product import operating_preset_for_space, operational_footprint_for_space


SECTION_KEYS = ("preparation", "upcoming", "active", "blocked", "completed")
PREVIEW_LIMIT = 20


def _space_has_activity_portfolio_access(profile, space):
    return (
        has_direct_space_permission(profile, space, PermissionCode.SPACE_ACTIVITIES_VIEW)
        or has_direct_space_permission(profile, space, PermissionCode.SPACE_ACTIVITIES_MANAGE)
    )


def _mandated_activity_ids(profile, space):
    return set(
        current_mandates()
        .filter(
            profile=profile,
            scope_type=AuthorityScope.ACTIVITY,
            activity__space=space,
        )
        .exclude(activity_id=None)
        .values_list("activity_id", flat=True)
    )


def _visible_activity_ids(profile, space):
    if _space_has_activity_portfolio_access(profile, space):
        return set(space.activities.values_list("pk", flat=True))
    return _mandated_activity_ids(profile, space)


def _activity_capability_sets(profile, space):
    return {
        "manage": set(activity_ids_with_direct_permission(profile, PermissionCode.ACTIVITY_MANAGE)),
        "operations": set(activity_ids_with_direct_permission(profile, PermissionCode.ACTIVITY_OPERATIONS_VIEW)),
        "commerce": set(activity_ids_with_direct_permission(profile, PermissionCode.ACTIVITY_COMMERCE_VIEW)),
        "service_cases": set(
            activity_ids_with_direct_permission(
                profile, PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ALL
            )
        )
        | set(
            activity_ids_with_direct_permission(
                profile, PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ASSIGNED
            )
        ),
    }


def _capabilities_for_activity(activity_id, caps):
    result = ["view"]
    if activity_id in caps["manage"]:
        result.append("manage")
    if activity_id in caps["operations"]:
        result.append("open_operations")
    if activity_id in caps["commerce"]:
        result.append("open_commerce")
    if activity_id in caps["service_cases"]:
        result.append("open_service_cases")
    return result


def _activity_item(activity, caps):
    return {
        "key": f"activity:{activity.pk}",
        "source": {"kind": "activity", "id": str(activity.pk)},
        "kind": "activity",
        "title": activity.title,
        "summary": activity.short_description or None,
        "timing": {},
        "state": activity.status,
        "context": {},
        "links": {"detail": f"/api/v1/activities/{activity.pk}/"},
        "capabilities": _capabilities_for_activity(activity.pk, caps),
    }


def _occurrence_item(occurrence, caps):
    return {
        "key": f"occurrence:{occurrence.pk}",
        "source": {"kind": "occurrence", "id": str(occurrence.pk)},
        "kind": "occurrence",
        "title": occurrence.label or occurrence.activity.title,
        "summary": occurrence.activity.short_description or None,
        "timing": {
            "kind": occurrence.timing_kind,
            "start_date": occurrence.start_date,
            "start_time": occurrence.start_time,
            "end_date": occurrence.end_date,
            "end_time": occurrence.end_time,
            "timezone": occurrence.timezone,
        },
        "state": occurrence.status,
        "context": {
            "activity": {
                "id": str(occurrence.activity_id),
                "title": occurrence.activity.title,
            }
        },
        "links": {
            "detail": f"/api/v1/occurrences/{occurrence.pk}/",
            "activity": f"/api/v1/activities/{occurrence.activity_id}/",
        },
        "capabilities": _capabilities_for_activity(occurrence.activity_id, caps),
    }


def _bounded(queryset, serializer):
    rows = list(queryset[: PREVIEW_LIMIT + 1])
    return {
        "items": [serializer(row) for row in rows[:PREVIEW_LIMIT]],
        "has_more": len(rows) > PREVIEW_LIMIT,
        "links": {},
    }


def _empty_section():
    return {"items": [], "has_more": False, "links": {}}


def _activity_scope_from_responsibility(profile, space, responsibility_key):
    if not responsibility_key or responsibility_key == "all":
        return None
    prefix = "mandate:"
    if not responsibility_key.startswith(prefix):
        return set()
    mandate_id = responsibility_key[len(prefix) :]
    mandate = (
        current_mandates()
        .filter(profile=profile, pk=mandate_id)
        .filter(
            Q(scope_type=AuthorityScope.SPACE, space=space)
            | Q(scope_type=AuthorityScope.ACTIVITY, activity__space=space)
        )
        .first()
    )
    if mandate is None:
        return set()
    if mandate.scope_type == AuthorityScope.ACTIVITY:
        return {mandate.activity_id}
    return None


def build_space_work_projection(*, profile, space, responsibility_key=None):
    visible_ids = _visible_activity_ids(profile, space)
    lens_ids = _activity_scope_from_responsibility(
        profile, space, responsibility_key
    )
    if lens_ids == set():
        return None
    if lens_ids is not None:
        visible_ids &= lens_ids

    preset = operating_preset_for_space(space)
    caps = _activity_capability_sets(profile, space)
    activities = Activity.objects.filter(space=space, pk__in=visible_ids)
    occurrences = Occurrence.objects.filter(
        activity__space=space,
        activity_id__in=visible_ids,
    ).select_related("activity")
    now = timezone.now()
    today = timezone.localdate()

    sections = {key: _empty_section() for key in SECTION_KEYS}

    preparation_activities = activities.filter(status=ActivityStatus.DRAFT).order_by(
        "title", "pk"
    )
    preparation_occurrences = occurrences.filter(
        status=OccurrenceStatus.DRAFT
    ).order_by("start_date", "start_time", "pk")
    preparation_rows = [
        *_bounded(preparation_activities, lambda row: _activity_item(row, caps))["items"],
        *_bounded(preparation_occurrences, lambda row: _occurrence_item(row, caps))["items"],
    ][:PREVIEW_LIMIT]
    sections["preparation"] = {
        "items": preparation_rows,
        "has_more": (
            preparation_activities.count() + preparation_occurrences.count()
            > PREVIEW_LIMIT
        ),
        "links": {},
    }

    sections["upcoming"] = _bounded(
        occurrences.filter(
            status=OccurrenceStatus.SCHEDULED,
        ).filter(
            Q(start_at__gt=now)
            | Q(start_at__isnull=True, start_date__gt=today)
        ).order_by("start_date", "start_time", "pk"),
        lambda row: _occurrence_item(row, caps),
    )

    active_occurrences = occurrences.filter(status=OccurrenceStatus.SCHEDULED).filter(
        Q(start_at__lte=now, end_at__gt=now)
        | Q(start_at__lte=now, end_at__isnull=True)
        | Q(
            start_at__isnull=True,
            timing_kind="all_day",
            start_date__lte=today,
            end_date__gte=today,
        )
        | Q(
            start_at__isnull=True,
            timing_kind="all_day",
            start_date=today,
            end_date__isnull=True,
        )
    )
    active_activities = activities.filter(status=ActivityStatus.PUBLISHED).order_by(
        "title", "pk"
    )
    active_rows = [
        *_bounded(active_occurrences.order_by("start_date", "start_time", "pk"), lambda row: _occurrence_item(row, caps))["items"],
        *_bounded(active_activities, lambda row: _activity_item(row, caps))["items"],
    ][:PREVIEW_LIMIT]
    sections["active"] = {
        "items": active_rows,
        "has_more": active_occurrences.count() + active_activities.count() > PREVIEW_LIMIT,
        "links": {},
    }

    completed_occurrences = occurrences.filter(
        status=OccurrenceStatus.COMPLETED
    ).order_by("-start_date", "-start_time", "pk")
    completed_activities = activities.filter(
        status=ActivityStatus.COMPLETED
    ).order_by("-updated_at", "pk")
    completed_rows = [
        *_bounded(completed_occurrences, lambda row: _occurrence_item(row, caps))["items"],
        *_bounded(completed_activities, lambda row: _activity_item(row, caps))["items"],
    ][:PREVIEW_LIMIT]
    sections["completed"] = {
        "items": completed_rows,
        "has_more": completed_occurrences.count() + completed_activities.count() > PREVIEW_LIMIT,
        "links": {},
    }

    direct_portfolio = _space_has_activity_portfolio_access(profile, space)
    footprint = (
        list(operational_footprint_for_space(space).signals)
        if direct_portfolio
        else []
    )

    return {
        "space": {
            "id": str(space.pk),
            "slug": space.slug,
            "name": space.name,
        },
        "archetype": space.archetype,
        "primary_business_label": preset.primary_business_label,
        "authority": {
            "scope": "space" if direct_portfolio else "activity_limited",
            "limited_to_activities": not direct_portfolio,
        },
        "responsibility": responsibility_key or "all",
        "operational_footprint": {"signals": footprint},
        "sections": sections,
        "links": {
            "workspace": f"/api/v1/organizations/workspaces/{space.slug}/",
        },
        "capabilities": {
            "create_activity": has_direct_space_permission(
                profile, space, PermissionCode.SPACE_ACTIVITIES_MANAGE
            ),
        },
    }
