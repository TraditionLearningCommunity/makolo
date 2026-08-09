from django.urls import path

from .views import (
    FollowingListView,
    OrganizationCreateView,
    OrganizationDetailView,
    OrganizationListView,
    OrganizationMemberCreateView,
    OrganizationMemberDeactivateView,
    OrganizationUpdateView,
)


app_name = "organizations"

urlpatterns = [
    path("", OrganizationListView.as_view(), name="list"),
    path("following/", FollowingListView.as_view(), name="following"),
    path("new/", OrganizationCreateView.as_view(), name="create"),
    path("<slug:slug>/", OrganizationDetailView.as_view(), name="detail"),
    path("<slug:slug>/edit/", OrganizationUpdateView.as_view(), name="edit"),
    path("<slug:slug>/members/new/", OrganizationMemberCreateView.as_view(), name="member-create"),
    path(
        "<slug:slug>/members/<uuid:pk>/deactivate/",
        OrganizationMemberDeactivateView.as_view(),
        name="member-deactivate",
    ),
]
