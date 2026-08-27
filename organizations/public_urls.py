from django.urls import path

from .profile_follow_views import ProfileFollowingListView, ProfileFollowView
from .public_views import PublicOrganizationListView
from .views import (
    OrganizationFollowPreferencesView,
    OrganizationFollowToggleView,
    PublicOrganizationDetailView,
)


app_name = "organizer_public"

urlpatterns = [
    path("", PublicOrganizationListView.as_view(), name="list"),
    path("profiles/following/", ProfileFollowingListView.as_view(), name="profile-following"),
    path("profiles/<uuid:profile_id>/follow/", ProfileFollowView.as_view(), name="profile-follow"),
    path("<slug:slug>/", PublicOrganizationDetailView.as_view(), name="detail"),
    path("<slug:slug>/follow/", OrganizationFollowToggleView.as_view(), name="follow-toggle"),
    path("<slug:slug>/preferences/", OrganizationFollowPreferencesView.as_view(), name="follow-preferences"),
]
