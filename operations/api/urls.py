from django.urls import path

from operations.placement_api import (
    MyOccurrencePlacementsAPIView,
    OperatorOccurrencePlacementPlansAPIView,
    PlacementAssignmentDetailAPIView,
    PlacementAssignmentsAPIView,
)

from .views import (
    EventModerationAPIView,
    ModerationCasesAPIView,
    OperationsEventsAPIView,
    OperationsIncidentDetailAPIView,
    OperationsIncidentsAPIView,
    OperationsOrganizationsAPIView,
    OperationsOverviewAPIView,
    OrganizationDecisionAPIView,
    WorkerHealthAPIView,
)


app_name = "operations_api"

urlpatterns = [
    path("overview/", OperationsOverviewAPIView.as_view(), name="overview"),
    path("organizations/", OperationsOrganizationsAPIView.as_view(), name="organizations"),
    path("organizations/<uuid:pk>/review/", OrganizationDecisionAPIView.as_view(), name="organization-review"),
    path("events/", OperationsEventsAPIView.as_view(), name="events"),
    path("events/<uuid:pk>/moderate/", EventModerationAPIView.as_view(), name="event-moderate"),
    path("incidents/", OperationsIncidentsAPIView.as_view(), name="incidents"),
    path("incidents/<uuid:pk>/", OperationsIncidentDetailAPIView.as_view(), name="incident-detail"),
    path("moderation/", ModerationCasesAPIView.as_view(), name="moderation"),
    path("workers/", WorkerHealthAPIView.as_view(), name="workers"),
    path(
        "occurrences/<uuid:occurrence_id>/placements/me/",
        MyOccurrencePlacementsAPIView.as_view(),
        name="occurrence-placement-me",
    ),
    path(
        "occurrences/<uuid:occurrence_id>/placement-plans/",
        OperatorOccurrencePlacementPlansAPIView.as_view(),
        name="occurrence-placement-plans",
    ),
    path(
        "placement-plans/<uuid:plan_id>/assignments/",
        PlacementAssignmentsAPIView.as_view(),
        name="placement-assignments",
    ),
    path(
        "placement-assignments/<uuid:assignment_id>/",
        PlacementAssignmentDetailAPIView.as_view(),
        name="placement-assignment-detail",
    ),
]
