from django.urls import path

from interoperability.api_views import SpaceInteroperabilityAPIView

from .space_mark_views import SpaceMarkAPIView
from .space_work_views import SpaceWorkAPIView
from .space_zs4_views import SpacePilotAPIView, SpaceRelationshipsAPIView, SpaceUsAPIView
from .views import FollowDetailAPIView, FollowListCreateAPIView
from .workspace_views import (
    SpaceArchiveAPIView,
    SpaceOwnershipTransferAPIView,
    SpaceRestoreAPIView,
    SpaceTeamAPIView,
    SpaceTeamMemberAPIView,
    SpaceWorkspaceDetailAPIView,
    SpaceWorkspaceListAPIView,
)


app_name = "organizations_api"

urlpatterns = [
    path("workspaces/", SpaceWorkspaceListAPIView.as_view(), name="workspaces"),
    path("workspaces/<slug:slug>/", SpaceWorkspaceDetailAPIView.as_view(), name="workspace-detail"),
    path("workspaces/<slug:slug>/work/", SpaceWorkAPIView.as_view(), name="workspace-work"),
    path("workspaces/<slug:slug>/us/", SpaceUsAPIView.as_view(), name="workspace-us"),
    path("workspaces/<slug:slug>/relationships/", SpaceRelationshipsAPIView.as_view(), name="workspace-relationships"),
    path("workspaces/<slug:slug>/pilot/", SpacePilotAPIView.as_view(), name="workspace-pilot"),
    path("workspaces/<slug:slug>/archive/", SpaceArchiveAPIView.as_view(), name="workspace-archive"),
    path("workspaces/<slug:slug>/restore/", SpaceRestoreAPIView.as_view(), name="workspace-restore"),
    path("workspaces/<slug:slug>/ownership/transfer/", SpaceOwnershipTransferAPIView.as_view(), name="workspace-ownership-transfer"),
    path("workspaces/<slug:slug>/team/", SpaceTeamAPIView.as_view(), name="workspace-team"),
    path("workspaces/<slug:slug>/team/<uuid:membership_id>/", SpaceTeamMemberAPIView.as_view(), name="workspace-team-member"),
    path("workspaces/<slug:slug>/interoperability/", SpaceInteroperabilityAPIView.as_view(), name="workspace-interoperability"),
    path("workspaces/<slug:slug>/mark/", SpaceMarkAPIView.as_view(), name="workspace-mark"),
    path("follows/", FollowListCreateAPIView.as_view(), name="follows"),
    path("follows/<uuid:pk>/", FollowDetailAPIView.as_view(), name="follow-detail"),
]
