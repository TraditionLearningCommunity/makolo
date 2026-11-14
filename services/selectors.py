from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from authorization.constants import PermissionCode
from authorization.services import activity_ids_with_permission, can
from journeys.collaboration_models import (
    JourneyArtifact,
    JourneyArtifactSensitivity,
    JourneyAssignmentStatus,
    JourneyNote,
    JourneyNoteVisibility,
)
from journeys.models import Journey, WorkflowKind

from .models import ServiceOutcomeEvent, ServiceSubmission


def submissions_for_context(context):
    return (
        ServiceSubmission.objects.filter(context=context)
        .select_related("context", "context__journey", "receipt_artifact", "submitted_by")
        .order_by("attempt", "created_at", "id")
    )


def latest_submission(context):
    return submissions_for_context(context).order_by("-attempt", "-created_at", "-id").first()


def outcome_timeline(context):
    return (
        ServiceOutcomeEvent.objects.filter(context=context)
        .select_related("context", "recorded_by")
        .order_by("occurred_at", "created_at", "id")
    )


def current_outcome(context):
    return context.current_outcome


def service_journeys_visible_to(profile):
    """DB-first union of beneficiary, view-all and active-assignment Services cases."""
    if not getattr(profile, "is_authenticated", False):
        return Journey.objects.none()
    queryset = Journey.objects.filter(workflow=WorkflowKind.SERVICE)

    view_all_activity_ids = activity_ids_with_permission(
        profile,
        PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ALL,
    )
    if view_all_activity_ids is None:
        return queryset.select_related("activity", "beneficiary").order_by("-created_at", "id")

    filters = Q(beneficiary=profile)
    if view_all_activity_ids:
        filters |= Q(activity_id__in=view_all_activity_ids)

    view_assigned_activity_ids = activity_ids_with_permission(
        profile,
        PermissionCode.ACTIVITY_SERVICES_CASES_VIEW_ASSIGNED,
    )
    if view_assigned_activity_ids is None:
        filters |= Q(assignments__profile=profile, assignments__status=JourneyAssignmentStatus.ACTIVE)
    elif view_assigned_activity_ids:
        filters |= Q(
            activity_id__in=view_assigned_activity_ids,
            assignments__profile=profile,
            assignments__status=JourneyAssignmentStatus.ACTIVE,
        )

    return (
        queryset.filter(filters)
        .select_related("activity", "beneficiary")
        .distinct()
        .order_by("-created_at", "id")
    )


def service_artifacts_visible_to(profile, *, journey):
    visible_journeys = service_journeys_visible_to(profile).filter(pk=journey.pk)
    if not visible_journeys.exists():
        return JourneyArtifact.objects.none()
    queryset = JourneyArtifact.objects.filter(journey=journey).select_related("step", "uploaded_by")
    if journey.beneficiary_id == getattr(profile, "pk", None):
        return queryset
    if not can(profile, PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_VIEW, activity=journey.activity):
        return queryset.none()
    if not can(profile, PermissionCode.ACTIVITY_SERVICES_ARTIFACTS_RESTRICTED_VIEW, activity=journey.activity):
        queryset = queryset.exclude(sensitivity=JourneyArtifactSensitivity.RESTRICTED)
    return queryset


def service_notes_visible_to(profile, *, journey):
    visible_journeys = service_journeys_visible_to(profile).filter(pk=journey.pk)
    if not visible_journeys.exists():
        return JourneyNote.objects.none()
    queryset = JourneyNote.objects.filter(journey=journey).select_related("author", "step")
    if journey.beneficiary_id == getattr(profile, "pk", None):
        return queryset.filter(visibility=JourneyNoteVisibility.BENEFICIARY_VISIBLE)
    if not can(profile, PermissionCode.ACTIVITY_SERVICES_NOTES_INTERNAL, activity=journey.activity):
        return queryset.filter(visibility=JourneyNoteVisibility.BENEFICIARY_VISIBLE)
    return queryset


def service_opportunity_relation_for_viewer(*, journey_id, viewer) -> dict | None:
    """Read an existing Journey -> Opportunity relationship with owner authority.

    Only a viewer permitted to see the Service Journey may receive the
    identifiers. The pinned published revision remains the historical basis,
    even if the Opportunity later changes. This does not grant rights to the
    linked Opportunity or create a public Discovery graph.
    """
    journey = (
        service_journeys_visible_to(viewer)
        .select_related("service_context", "service_context__opportunity_revision")
        .filter(pk=journey_id)
        .first()
    )
    if journey is None:
        return None
    try:
        context = journey.service_context
    except ObjectDoesNotExist:
        return None
    if not context.opportunity_id or not context.opportunity_revision_id:
        return None
    return {
        "kind": "service_journey_opportunity",
        "members": [
            {"kind": "journey", "id": str(journey.pk)},
            {"kind": "opportunity", "id": str(context.opportunity_id)},
        ],
        "basis": {"kind": "service_journey_context", "id": str(context.pk)},
        "revision": {
            "kind": "opportunity_revision",
            "id": str(context.opportunity_revision_id),
        },
    }
