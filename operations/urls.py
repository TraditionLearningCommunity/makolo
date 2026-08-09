from django.urls import path

from .views import (
    EventModerationView,
    ModerationQueueView,
    OperationsDashboardView,
    OperationsEventsView,
    OperationsIncidentCreateView,
    OperationsIncidentDetailView,
    OperationsIncidentsView,
    OperationsOrganizationsView,
    OrganizationReviewView,
)


app_name = "operations"

urlpatterns = [
    path("", OperationsDashboardView.as_view(), name="dashboard"),
    path("organizations/", OperationsOrganizationsView.as_view(), name="organizations"),
    path("organizations/<uuid:pk>/review/", OrganizationReviewView.as_view(), name="organization-review"),
    path("events/", OperationsEventsView.as_view(), name="events"),
    path("events/<uuid:pk>/moderate/", EventModerationView.as_view(), name="event-moderate"),
    path("incidents/", OperationsIncidentsView.as_view(), name="incidents"),
    path("incidents/new/", OperationsIncidentCreateView.as_view(), name="incident-new"),
    path("incidents/<uuid:pk>/", OperationsIncidentDetailView.as_view(), name="incident-detail"),
    path("moderation/", ModerationQueueView.as_view(), name="moderation"),
]
