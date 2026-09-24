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
    capacity_availability_many,
    pools_for_activity,
    pools_for_occurrence,
)
from core.api.projections import projection_envelope
from core.participant_activity_context import participant_state_context_for_activities
from core.participant_presentation import resolve_participant_activity_state
from core.participant_selectors import participant_state_context
from core.product_language import vocabulary_for
from operations.participant_occurrence_live import participant_occurrence_live_available
from organizations.models import OrganizationVerificationStatus


PUBLIC_ACTIVITY_STATUSES = {
    ActivityStatus.PUBLISHED,
    ActivityStatus.CANCELLED,
    ActivityStatus.COMPLETED,
}
DIRECT_ACTIVITY_VISIBILITIES = {
    ActivityVisibility.PUBLIC,
    ActivityVisibility.UNLISTED,
}
PUBLIC_OCCURRENCE_STATUSES = {
    OccurrenceStatus.SCHEDULED,
    OccurrenceStatus.CANCELLED,
    OccurrenceStatus.COMPLETED,
}

ACTIVITY_DETAIL_OCCURRENCE_LIMIT = 50


def _authenticated(user):
    return bool(getattr(user, "is_authenticated", False))


def _public_activity_detail_filter():
    return (
        Q(
            visibility__in=DIRECT_ACTIVITY_VISIBILITIES,
            status__in=PUBLIC_ACTIVITY_STATUSES,
        )
        & (
            Q(space__isnull=True)
            | ~Q(space__verification_status=OrganizationVerificationStatus.SUSPENDED)
        )
    )


def _participant_activity_filter(user):
    return Q(journeys__beneficiary=user) | Q(access_rights__beneficiary=user)


def _visible_activity_queryset(user):
    queryset = Activity.objects.select_related(
        "space",
        "owner_profile",
        "event_vertical",
    ).prefetch_related(
        "occurrences__place_links__place",
    )
    public = _public_activity_detail_filter()
    if not _authenticated(user):
        return queryset.filter(public).distinct()

    allowed = activity_ids_with_permission(user, PermissionCode.ACTIVITY_VIEW)
    if allowed is None:
        return queryset
    contextual = Q(pk__in=allowed) if allowed else Q(pk__isnull=True)
    return queryset.filter(
        public
        | Q(owner_profile=user)
        | contextual
        | _participant_activity_filter(user)
    ).distinct()


def _has_structural_activity_visibility(user, activity):
    if not _authenticated(user):
        return False
    if activity.owner_profile_id == getattr(user, "pk", None):
        return True
    allowed = activity_ids_with_permission(user, PermissionCode.ACTIVITY_VIEW)
    return allowed is None or activity.pk in set(allowed)


def _visible_occurrence_queryset(user):
    queryset = Occurrence.objects.select_related(
        "activity",
        "activity__space",
        "activity__owner_profile",
        "activity__event_vertical",
    ).prefetch_related("place_links__place")
    public = Q(
        status__in=PUBLIC_OCCURRENCE_STATUSES,
        activity__visibility__in=DIRECT_ACTIVITY_VISIBILITIES,
        activity__status__in=PUBLIC_ACTIVITY_STATUSES,
    ) & (
        Q(activity__space__isnull=True)
        | ~Q(
            activity__space__verification_status=OrganizationVerificationStatus.SUSPENDED
        )
    )
    if not _authenticated(user):
        return queryset.filter(public).distinct()

    allowed = activity_ids_with_permission(user, PermissionCode.ACTIVITY_VIEW)
    if allowed is None:
        return queryset
    contextual = Q(activity_id__in=allowed) if allowed else Q(pk__isnull=True)
    return queryset.filter(
        public
        | Q(activity__owner_profile=user)
        | contextual
        | Q(
            status__in=PUBLIC_OCCURRENCE_STATUSES,
            journeys__beneficiary=user,
        )
        | Q(
            status__in=PUBLIC_OCCURRENCE_STATUSES,
            access_rights__beneficiary=user,
        )
        | Q(
            status__in=PUBLIC_OCCURRENCE_STATUSES,
            activity__journeys__beneficiary=user,
            activity__journeys__occurrence__isnull=True,
        )
        | Q(
            status__in=PUBLIC_OCCURRENCE_STATUSES,
            activity__access_rights__beneficiary=user,
            activity__access_rights__occurrence__isnull=True,
        )
    ).distinct()


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
    pools = [pool for pool in pools if pool.is_active]
    availability_by_id = capacity_availability_many(pools, now=now)
    result = []
    for pool in pools:
        availability = availability_by_id[pool.pk]
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
        public_detail = (
            activity.visibility in DIRECT_ACTIVITY_VISIBILITIES
            and activity.status in PUBLIC_ACTIVITY_STATUSES
            and (
                activity.space_id is None
                or activity.space.verification_status
                != OrganizationVerificationStatus.SUSPENDED
            )
        )
        structural_visibility = _has_structural_activity_visibility(
            request.user,
            activity,
        )
        occurrence_queryset = activity.occurrences.prefetch_related(
            "place_links__place"
        ).order_by(
            "start_date",
            "start_time",
            "id",
        )
        if not structural_visibility:
            occurrence_queryset = occurrence_queryset.filter(
                status__in=PUBLIC_OCCURRENCE_STATUSES
            )
        occurrence_rows = list(
            occurrence_queryset[: ACTIVITY_DETAIL_OCCURRENCE_LIMIT + 1]
        )
        occurrence_has_more = (
            len(occurrence_rows) > ACTIVITY_DETAIL_OCCURRENCE_LIMIT
        )
        occurrences = occurrence_rows[:ACTIVITY_DETAIL_OCCURRENCE_LIMIT]
        visible_occurrence_ids = {row.pk for row in occurrences}
        pools = [
            pool
            for pool in pools_for_activity(activity)
            if pool.occurrence_id is None or pool.occurrence_id in visible_occurrence_ids
        ]
        capacity = _capacity_rows(pools, now=observed_at)
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
            "occurrences_page": {
                "limit": ACTIVITY_DETAIL_OCCURRENCE_LIMIT,
                "returned": len(occurrences),
                "has_more": occurrence_has_more,
            },
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
                scope="authorized" if structural_visibility or not public_detail else "public",
            )
        )


class OccurrenceDetailAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk):
        observed_at = timezone.now()
        occurrence = get_object_or_404(_visible_occurrence_queryset(request.user), pk=pk)
        activity = occurrence.activity
        public_detail = (
            activity.visibility in DIRECT_ACTIVITY_VISIBILITIES
            and activity.status in PUBLIC_ACTIVITY_STATUSES
            and occurrence.status in PUBLIC_OCCURRENCE_STATUSES
            and (
                activity.space_id is None
                or activity.space.verification_status
                != OrganizationVerificationStatus.SUSPENDED
            )
        )
        structural_visibility = _has_structural_activity_visibility(
            request.user,
            activity,
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

        live_available = (
            participant_occurrence_live_available(
                occurrence=occurrence,
                actor=request.user,
            )
            if _authenticated(request.user)
            else False
        )
        live_link = None
        capabilities = []
        if live_available:
            live_link = f"/api/v1/operations/occurrences/{occurrence.pk}/live/"
            capabilities.append("open_live")

        links = {
            "self": f"/api/v1/occurrences/{occurrence.pk}/",
            "activity": f"/api/v1/activities/{activity.pk}/",
        }
        if live_link:
            links["day_of"] = f"/api/v1/me/occurrences/{occurrence.pk}/day-of/"
            links["live"] = live_link
            capabilities.append("open_day_of")

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
                scope="authorized" if structural_visibility or not public_detail else "public",
            )
        )
