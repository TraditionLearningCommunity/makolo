from django.urls import path

from .views import (
    OrganizationFollowPreferencesView,
    OrganizationFollowToggleView,
    PublicOrganizationDetailView,
)


app_name = "organizer_public"

urlpatterns = [
    path("<slug:slug>/", PublicOrganizationDetailView.as_view(), name="detail"),
    path("<slug:slug>/follow/", OrganizationFollowToggleView.as_view(), name="follow-toggle"),
    path("<slug:slug>/preferences/", OrganizationFollowPreferencesView.as_view(), name="follow-preferences"),
]
