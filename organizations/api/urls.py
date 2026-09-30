from django.urls import path

from interoperability.api_views import SpaceInteroperabilityAPIView

from .views import FollowDetailAPIView, FollowListCreateAPIView
from .workspace_views import (
    SpaceArchiveAPIView,
    SpaceOwnershipTransferAPIView,
    SpaceRestoreAPIView,
    SpaceWorkspaceDetailAPIView,
    SpaceWorkspaceListAPIView,
)


app_name = "organizations_api"

urlpatterns = [
    path("workspaces/", SpaceWorkspaceListAPIView.as_view(), name="workspaces"),
    path("workspaces/<slug:slug>/", SpaceWorkspaceDetailAPIView.as_view(), name="workspace-detail"),
    path("workspaces/<slug:slug>/archive/", SpaceArchiveAPIView.as_view(), name="workspace-archive"),
    path("workspaces/<slug:slug>/restore/", SpaceRestoreAPIView.as_view(), name="workspace-restore"),
    path("workspaces/<slug:slug>/ownership/transfer/", SpaceOwnershipTransferAPIView.as_view(), name="workspace-ownership-transfer"),
    path("workspaces/<slug:slug>/interoperability/", SpaceInteroperabilityAPIView.as_view(), name="workspace-interoperability"),
    path("follows/", FollowListCreateAPIView.as_view(), name="follows"),
    path("follows/<uuid:pk>/", FollowDetailAPIView.as_view(), name="follow-detail"),
]
