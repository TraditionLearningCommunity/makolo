from django.urls import path

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
]
