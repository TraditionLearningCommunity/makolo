from django.urls import path

from .views import (
    CRMWorkflowActionCreateView,
    CRMWorkflowActionToggleView,
    CRMWorkflowCreateView,
    CRMWorkflowDetailView,
    CRMWorkflowListView,
    CRMWorkflowToggleView,
    CRMWorkflowUpdateView,
    EventAutomationPolicyView,
)


app_name = "automation"

urlpatterns = [
    path("events/<slug:slug>/", EventAutomationPolicyView.as_view(), name="event-policy"),
    path("crm/<slug:slug>/", CRMWorkflowListView.as_view(), name="crm-workflows"),
    path("crm/<slug:slug>/new/", CRMWorkflowCreateView.as_view(), name="crm-workflow-create"),
    path("crm/workflows/<uuid:pk>/", CRMWorkflowDetailView.as_view(), name="crm-workflow-detail"),
    path("crm/workflows/<uuid:pk>/edit/", CRMWorkflowUpdateView.as_view(), name="crm-workflow-edit"),
    path("crm/workflows/<uuid:pk>/toggle/", CRMWorkflowToggleView.as_view(), name="crm-workflow-toggle"),
    path("crm/workflows/<uuid:pk>/actions/", CRMWorkflowActionCreateView.as_view(), name="crm-workflow-action-create"),
    path("crm/workflows/<uuid:pk>/actions/<uuid:action_id>/toggle/", CRMWorkflowActionToggleView.as_view(), name="crm-workflow-action-toggle"),
]
