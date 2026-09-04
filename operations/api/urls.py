from django.urls import path

from operations.checkpoint_api import (
    CheckpointAssignmentDetailAPIView,
    CheckpointAssignmentsAPIView,
    CheckpointObservationsAPIView,
    CheckpointStatusAPIView,
    MyOccurrenceCheckpointsAPIView,
    OperatorOccurrenceCheckpointsAPIView,
)
from operations.live_api import OccurrenceLiveAPIView, OccurrenceOperationalReadinessAPIView
from operations.placement_api import (
    MyOccurrencePlacementsAPIView,
    OperatorOccurrencePlacementPlansAPIView,
    PlacementAssignmentDetailAPIView,
    PlacementAssignmentsAPIView,
)
from operations.queue_api import (
    MyOccurrenceQueuesAPIView,
    MyQueueEntryAPIView,
    MyQueueEntryCancelAPIView,
    OperatorOccurrenceQueuesAPIView,
    QueueCallNextAPIView,
    QueueEntriesAPIView,
    QueueEntryActionAPIView,
    QueueStatusAPIView,
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
        "occurrences/<uuid:occurrence_id>/readiness/",
        OccurrenceOperationalReadinessAPIView.as_view(),
        name="occurrence-readiness",
    ),
    path(
        "occurrences/<uuid:occurrence_id>/live/",
        OccurrenceLiveAPIView.as_view(),
        name="occurrence-live",
    ),
    path(
        "occurrences/<uuid:occurrence_id>/queues/me/",
        MyOccurrenceQueuesAPIView.as_view(),
        name="occurrence-queues-me",
    ),
    path(
        "occurrences/<uuid:occurrence_id>/queues/",
        OperatorOccurrenceQueuesAPIView.as_view(),
        name="occurrence-queues",
    ),
    path("queues/<uuid:queue_id>/entries/", QueueEntriesAPIView.as_view(), name="queue-entries"),
    path("queues/<uuid:queue_id>/entries/me/", MyQueueEntryAPIView.as_view(), name="queue-entry-me"),
    path("queues/<uuid:queue_id>/call/", QueueCallNextAPIView.as_view(), name="queue-call-next"),
    path("queues/<uuid:queue_id>/status/", QueueStatusAPIView.as_view(), name="queue-status"),
    path(
        "queue-entries/<uuid:entry_id>/<str:action>/",
        QueueEntryActionAPIView.as_view(),
        name="queue-entry-action",
    ),
    path(
        "queue-entries/<uuid:entry_id>/me/cancel/",
        MyQueueEntryCancelAPIView.as_view(),
        name="queue-entry-me-cancel",
    ),
    path(
        "occurrences/<uuid:occurrence_id>/checkpoints/me/",
        MyOccurrenceCheckpointsAPIView.as_view(),
        name="occurrence-checkpoints-me",
    ),
    path(
        "occurrences/<uuid:occurrence_id>/checkpoints/",
        OperatorOccurrenceCheckpointsAPIView.as_view(),
        name="occurrence-checkpoints",
    ),
    path(
        "checkpoints/<uuid:checkpoint_id>/status/",
        CheckpointStatusAPIView.as_view(),
        name="checkpoint-status",
    ),
    path(
        "checkpoints/<uuid:checkpoint_id>/assignments/",
        CheckpointAssignmentsAPIView.as_view(),
        name="checkpoint-assignments",
    ),
    path(
        "checkpoint-assignments/<uuid:assignment_id>/",
        CheckpointAssignmentDetailAPIView.as_view(),
        name="checkpoint-assignment-detail",
    ),
    path(
        "checkpoints/<uuid:checkpoint_id>/observations/",
        CheckpointObservationsAPIView.as_view(),
        name="checkpoint-observations",
    ),
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
