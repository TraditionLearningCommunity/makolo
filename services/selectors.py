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
