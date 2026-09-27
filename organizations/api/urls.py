from django.urls import path

from .views import FollowDetailAPIView, FollowListCreateAPIView
from .workspace_views import SpaceWorkspaceDetailAPIView, SpaceWorkspaceListAPIView


app_name = "organizations_api"

urlpatterns = [
    path("workspaces/", SpaceWorkspaceListAPIView.as_view(), name="workspaces"),
    path("workspaces/<slug:slug>/", SpaceWorkspaceDetailAPIView.as_view(), name="workspace-detail"),
    path("follows/", FollowListCreateAPIView.as_view(), name="follows"),
    path("follows/<uuid:pk>/", FollowDetailAPIView.as_view(), name="follow-detail"),
]
