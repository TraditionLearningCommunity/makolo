from django.urls import path

from .access_views import PersonalAccessCredentialAPIView, PersonalAccessesAPIView
from .history_views import PersonalHistoryAPIView
from .day_of_views import PersonalOccurrenceDayOfAPIView
from .me_views import (
    PersonalCollectivesAPIView,
    PersonalConsiderationsAPIView,
    PersonalMeAPIView,
    PersonalPartnersAPIView,
    PersonalPassportAPIView,
    PersonalResourcesAPIView,
)
from .personal_views import PersonalNowAPIView, PersonalOngoingAPIView
from .z9_views import PersonalPartnerDetailAPIView
from .z8_views import (
    PersonalGroupDetailAPIView,
    PersonalResourceDetailAPIView,
    PersonalResourceVersionDownloadAPIView,
    PersonalResourceVersionReuseAPIView,
)


app_name = "personal-projections"

urlpatterns = [
    path("", PersonalMeAPIView.as_view(), name="me"),
    path("now/", PersonalNowAPIView.as_view(), name="now"),
    path("ongoing/", PersonalOngoingAPIView.as_view(), name="ongoing"),
    path("accesses/", PersonalAccessesAPIView.as_view(), name="accesses"),
    path("history/", PersonalHistoryAPIView.as_view(), name="history"),
    path(
        "occurrences/<uuid:pk>/day-of/",
        PersonalOccurrenceDayOfAPIView.as_view(),
        name="day-of",
    ),
    path(
        "accesses/<uuid:pk>/credential/",
        PersonalAccessCredentialAPIView.as_view(),
        name="access-credential",
    ),
    path(
        "considerations/",
        PersonalConsiderationsAPIView.as_view(),
        name="considerations",
    ),
    path(
        "collectives/",
        PersonalCollectivesAPIView.as_view(),
        name="collectives",
    ),
    path(
        "passport/",
        PersonalPassportAPIView.as_view(),
        name="passport",
    ),
    path(
        "resources/",
        PersonalResourcesAPIView.as_view(),
        name="resources",
    ),
    path(
        "resources/<uuid:pk>/",
        PersonalResourceDetailAPIView.as_view(),
        name="resource-detail",
    ),
    path(
        "resources/versions/<uuid:version_id>/download/",
        PersonalResourceVersionDownloadAPIView.as_view(),
        name="resource-version-download",
    ),
    path(
        "resources/versions/<uuid:version_id>/reuse/",
        PersonalResourceVersionReuseAPIView.as_view(),
        name="resource-version-reuse",
    ),
    path(
        "collectives/groups/<uuid:pk>/",
        PersonalGroupDetailAPIView.as_view(),
        name="group-detail",
    ),
    path(
        "partners/",
        PersonalPartnersAPIView.as_view(),
        name="partners",
    ),
    path(
        "partners/<uuid:pk>/",
        PersonalPartnerDetailAPIView.as_view(),
        name="partner-detail",
    ),
]
