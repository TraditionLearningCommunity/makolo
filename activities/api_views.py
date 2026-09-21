from __future__ import annotations

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from activities.models import (
    Activity,
    ActivityStatus,
    ActivityVisibility,
    Occurrence,
    OccurrenceStatus,
)
from activities.selectors import primary_place_for_occurrence
from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission
from capacity.selectors import (
    capacity_availability,
    pools_for_activity,
    pools_for_occurrence,
)
from core.api.projections import projection_envelope
from core.participant_activity_context import participant_state_context_for_activities
from core.participant_presentation import resolve_participant_activity_state
from core.participant_selectors import participant_state_context
from core.product_language import vocabulary_for
from operations.participant_occurrence_live import resolve_participant_occurrence_live


PUBLIC_ACTIVITY_STATUSES = {
    ActivityStatus.PUBLISHED,
    ActivityStatus.CANCELLED,
    ActivityStatus.COMPLETED,
}
PUBLIC_OCCURRENCE_STATUSES = {
    OccurrenceStatus.SCHEDULED,
    OccurrenceStatus.CANCELLED,
    OccurrenceStatus.COMPLETED,
}


def _authenticated(user):
    return bool(getattr(user, "is_authenticated", False))


def _visible_activity_queryset(user):
    queryset = Activity.objects.select_related(
        "space",
        "owner_profile",
        "event_vertical",
    ).prefetch_related(
        "occurrences__place_links__place",
    )
    public = Q(
        visibility=ActivityVisibility.PUBLIC,
        status__in=PUBLIC_ACTIVITY_STATUSES,
    )
    if not _authenticated(user):
        return queryset.filter(public)

    allowed = activity_ids_with_permission(user, PermissionCode.ACTIVITY_MANAGE)
    if allowed is None:
        return queryset
    personal = Q(owner_profile=user)
    if allowed:
        personal |= Q(pk__in=allowed)
    return queryset.filter(public | personal).distinct()


def _visible_occurrence_queryset(user):
    activities = _visible_activity_queryset(user).values_list("pk", flat=True)
    queryset = Occurrence.objects.filter(activity_id__in=activities).select_related(
        "activity",
        "activity__space",
        "activity__owner_profile",
        "activity__event_vertical",
    ).prefetch_related("place_links__place")
    if not _authenticated(user):
        queryset = queryset.filter(status__in=PUBLIC_OCCURRENCE_STATUSES)
    return queryset


def _iso(value):
    return value.isoformat() if value is not None else None


def _date(value):
    return value.isoformat() if value is not None else None


def _time(value):
    return value.isoformat() if value is not None else None


def _owner(activity):
    if activity.space_id:
        return {
            "kind": "space",
            "id": str(activity.space_id),
            "display_name": activity.space.name,
        }
    if activity.owner_profile_id:
        display = activity.owner_profile.full_name or activity.owner_profile.username
        return {
            "kind": "profile",
            "id": str(activity.owner_profile_id),
            "display_name": display,
        }
    return None


def _capacity_rows(pools, *, now):
    result = []
    for pool in pools:
        if not pool.is_active:
            continue
        availability = capacity_availability(pool, now=now)
        state = (
            "unlimited"
            if availability.unlimited
            else "sold_out"
            if availability.sold_out
            else "available"
        )
        result.append(
            {
                "id": str(pool.pk),
                "label": pool.label or None,
                "occurrence_id": str(pool.occurrence_id) if pool.occurrence_id else None,
                "state": state,
                "total": availability.total,
                "available": availability.available,
                "unlimited": availability.unlimited,
                "sold_out": availability.sold_out,
            }
        )
    return result


def _availability_state(capacity_rows):
    if not capacity_rows:
        return "available"
    if any(row["unlimited"] for row in capacity_rows):
        return "unlimited"
    if all(row["sold_out"] for row in capacity_rows):
        return "sold_out"
    return "available"


def _personal_relation(*, user, activity, occurrence=None, availability_state="available"):
    if not _authenticated(user):
        return None
    if occurrence is None:
        context = participant_state_context_for_activities(user, [activity])
    else:
        context = participant_state_context(user, [occurrence])
    state = resolve_participant_activity_state(
        profile=user,
        activity=activity,
        occurrence=occurrence,
        context=context,
        availability_state=availability_state,
        availability_label={
            "sold_out": "Complet",
            "cancelled": "Annulé",
            "completed": "Terminé",
        }.get(availability_state, "Disponible"),
    )
    return {
        "state": state.participant_state,
        "availability": state.availability,
        "expires_at": _iso(state.expires_at),
    }


def _timing(occurrence):
    return {
        "kind": occurrence.timing_kind,
        "start_date": _date(occurrence.start_date),
        "start_time": _time(occurrence.start_time),
        "end_date": _date(occurrence.end_date),
        "end_time": _time(occurrence.end_time),
        "start_at": _iso(occurrence.start_at),
        "end_at": _iso(occurrence.end_at),
        "timezone": occurrence.timezone,
    }


def _place(occurrence):
    place = primary_place_for_occurrence(occurrence)
    if place is None:
        return None
    return {
        "id": str(place.pk),
        "name": place.name,
        "locality": place.locality,
        "latitude": str(place.latitude) if place.latitude is not None else None,
        "longitude": str(place.longitude) if place.longitude is not None else None,
    }


def _vocabulary(activity):
    row = vocabulary_for(activity=activity)
    return {
        "vertical": row.vertical,
        "activity_noun": row.activity_noun,
        "occurrence_noun": row.occurrence_noun,
    }


class ActivityDetailAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        observed_at = timezone.now()
        activity = get_object_or_404(_visible_activity_queryset(request.user), pk=pk)
        authorized_private = not (
            activity.visibility == ActivityVisibility.PUBLIC
            and activity.status in PUBLIC_ACTIVITY_STATUSES
        )
        occurrences = list(
            activity.occurrences.prefetch_related("place_links__place").order_by(
                "start_date",
                "start_time",
                "id",
            )
        )
        if not authorized_private:
            occurrences = [
                row for row in occurrences if row.status in PUBLIC_OCCURRENCE_STATUSES
            ]
        capacity = _capacity_rows(pools_for_activity(activity), now=observed_at)
        availability = (
            "cancelled"
            if activity.status == ActivityStatus.CANCELLED
            else "completed"
            if activity.status == ActivityStatus.COMPLETED
            else _availability_state(capacity)
        )
        data = {
            "identity": {
                "kind": "activity",
                "id": str(activity.pk),
                "vertical": vocabulary_for(activity=activity).vertical,
            },
            "representation": {
                "title": activity.title,
                "summary": activity.short_description or activity.description or None,
                "vocabulary": _vocabulary(activity),
            },
            "owner": _owner(activity),
            "state": {
                "code": activity.status,
                "visibility": activity.visibility,
            },
            "occurrences": [
                {
                    "kind": "occurrence",
                    "id": str(row.pk),
                    "label": row.label or None,
                    "state": row.status,
                    "timing": _timing(row),
                    "link": f"/api/v1/occurrences/{row.pk}/",
                }
                for row in occurrences
            ],
            "capacity": capacity,
            "availability": {"state": availability},
            "personal_relation": _personal_relation(
                user=request.user,
                activity=activity,
                availability_state=availability,
            ),
            "capabilities": [],
            "links": {
                "self": f"/api/v1/activities/{activity.pk}/",
            },
        }
        return Response(
            projection_envelope(
                projection="activity.detail",
                data=data,
                generated_at=observed_at,
                scope="authorized" if authorized_private else "public",
            )
        )


class OccurrenceDetailAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        observed_at = timezone.now()
        occurrence = get_object_or_404(_visible_occurrence_queryset(request.user), pk=pk)
        activity = occurrence.activity
        authorized_private = not (
            activity.visibility == ActivityVisibility.PUBLIC
            and activity.status in PUBLIC_ACTIVITY_STATUSES
            and occurrence.status in PUBLIC_OCCURRENCE_STATUSES
        )
        pools = list(pools_for_occurrence(occurrence))
        if not pools:
            pools = [
                pool
                for pool in pools_for_activity(activity)
                if pool.occurrence_id is None
            ]
        capacity = _capacity_rows(pools, now=observed_at)
        availability = (
            "cancelled"
            if occurrence.status == OccurrenceStatus.CANCELLED
            else "completed"
            if occurrence.status == OccurrenceStatus.COMPLETED
            else _availability_state(capacity)
        )
        relation = _personal_relation(
            user=request.user,
            activity=activity,
            occurrence=occurrence,
            availability_state=availability,
        )

        live = (
            resolve_participant_occurrence_live(
                occurrence=occurrence,
                actor=request.user,
                observed_at=observed_at,
            )
            if _authenticated(request.user)
            else None
        )
        live_link = None
        capabilities = []
        if live is not None:
            live_link = f"/api/v1/operations/occurrences/{occurrence.pk}/live/"
            capabilities.append("open_live")

        links = {
            "self": f"/api/v1/occurrences/{occurrence.pk}/",
            "activity": f"/api/v1/activities/{activity.pk}/",
        }
        if live_link:
            links["live"] = live_link

        data = {
            "identity": {"kind": "occurrence", "id": str(occurrence.pk)},
            "activity": {
                "kind": "activity",
                "id": str(activity.pk),
                "title": activity.title,
            },
            "state": {"code": occurrence.status},
            "timing": _timing(occurrence),
            "place": _place(occurrence),
            "capacity": capacity,
            "availability": {"state": availability},
            "personal_relation": relation,
            "capabilities": capabilities,
            "links": links,
        }
        return Response(
            projection_envelope(
                projection="occurrence.detail",
                data=data,
                generated_at=observed_at,
                scope="authorized" if authorized_private else "public",
            )
        )
