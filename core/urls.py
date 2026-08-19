from django.contrib.auth.views import LogoutView
from django.urls import path

from .participant_views import (
    ParticipantAccessDetailView,
    ParticipantAccessListView,
    ParticipantHomeView,
    ParticipantInvitationAcceptView,
    ParticipantInvitationDeclineView,
    ParticipantJourneyDetailView,
    ParticipantJourneyListView,
)
from .views import DashboardView, PublicHomeView, RateLimitedLoginView


app_name = "core"

urlpatterns = [
    path("login/", RateLimitedLoginView.as_view(), name="login"),
    path(
        "logout/",
        LogoutView.as_view(next_page="core:home"),
        name="logout",
    ),
    path("me/", ParticipantHomeView.as_view(), name="participant-home"),
    path("me/journeys/", ParticipantJourneyListView.as_view(), name="participant-journeys"),
    path(
        "me/journeys/<uuid:pk>/",
        ParticipantJourneyDetailView.as_view(),
        name="participant-journey-detail",
    ),
    path(
        "me/journeys/<uuid:pk>/invitation/accept/",
        ParticipantInvitationAcceptView.as_view(),
        name="participant-invitation-accept",
    ),
    path(
        "me/journeys/<uuid:pk>/invitation/decline/",
        ParticipantInvitationDeclineView.as_view(),
        name="participant-invitation-decline",
    ),
    path("me/accesses/", ParticipantAccessListView.as_view(), name="participant-accesses"),
    path(
        "me/accesses/<uuid:pk>/",
        ParticipantAccessDetailView.as_view(),
        name="participant-access-detail",
    ),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("", PublicHomeView.as_view(), name="home"),
]
