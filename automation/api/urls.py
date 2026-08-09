from django.urls import path

from .views import (
    CRMWorkflowActionCreateAPIView,
    CRMWorkflowDetailAPIView,
    CRMWorkflowListCreateAPIView,
    CRMWorkflowRunsAPIView,
    CRMWorkflowToggleAPIView,
)


app_name = "automation_api"

urlpatterns = [
    path("workflows/", CRMWorkflowListCreateAPIView.as_view(), name="workflow-list"),
    path("workflows/<uuid:pk>/", CRMWorkflowDetailAPIView.as_view(), name="workflow-detail"),
    path("workflows/<uuid:pk>/toggle/", CRMWorkflowToggleAPIView.as_view(), name="workflow-toggle"),
    path("workflows/<uuid:pk>/actions/", CRMWorkflowActionCreateAPIView.as_view(), name="workflow-actions"),
    path("workflows/<uuid:pk>/runs/", CRMWorkflowRunsAPIView.as_view(), name="workflow-runs"),
]
