from django.db.models import Prefetch

from journeys.models import Journey

from .models import PlacementAssignment, PlacementPlan
from .permissions import user_can_view_activity_operations


INELIGIBLE_JOURNEY_STATUSES = {"rejected", "cancelled", "expired"}


def get_operator_placement_plans(user, occurrence):
    queryset = (
        PlacementPlan.objects.filter(occurrence=occurrence)
        .select_related("occurrence", "occurrence__activity", "occurrence__activity__space")
        .prefetch_related(
            "units__parent",
            Prefetch(
                "assignments",
                queryset=PlacementAssignment.objects.filter(ended_at__isnull=True).select_related(
                    "unit", "profile", "external_beneficiary", "assigned_by"
                ),
                to_attr="active_assignments",
            ),
        )
    )
    if not user_can_view_activity_operations(user, occurrence.activity):
        return queryset.none()
    return queryset


def get_operator_placement_assignment(user, assignment_id):
    queryset = PlacementAssignment.objects.select_related(
        "plan",
        "plan__occurrence",
        "plan__occurrence__activity",
        "plan__occurrence__activity__space",
        "unit",
        "unit__parent",
        "profile",
        "external_beneficiary",
        "assigned_by",
    )
    assignment = queryset.filter(pk=assignment_id).first()
    if assignment is None:
        return None
    if not user_can_view_activity_operations(user, assignment.plan.occurrence.activity):
        return None
    return assignment


def get_profile_occurrence_placements(profile, occurrence):
    if not profile or not profile.is_authenticated:
        return PlacementAssignment.objects.none()
    return PlacementAssignment.objects.filter(
        plan__occurrence=occurrence,
        plan__active=True,
        profile=profile,
        ended_at__isnull=True,
    ).select_related("plan", "unit", "unit__parent", "assigned_by")


def profile_is_placement_candidate(profile, occurrence):
    return Journey.objects.filter(
        beneficiary=profile,
        activity=occurrence.activity,
        occurrence=occurrence,
    ).exclude(status__in=INELIGIBLE_JOURNEY_STATUSES).exists()


def external_beneficiary_is_placement_candidate(external_beneficiary, occurrence):
    return Journey.objects.filter(
        external_beneficiary=external_beneficiary,
        activity=occurrence.activity,
        occurrence=occurrence,
    ).exclude(status__in=INELIGIBLE_JOURNEY_STATUSES).exists()
