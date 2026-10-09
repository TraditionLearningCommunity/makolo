from django.urls import path

from .access_views import PersonalAccessCredentialAPIView, PersonalAccessesAPIView
from .history_views import PersonalHistoryAPIView
from .search_views import PersonalSearchAPIView
from interoperability.api_views import PersonalInteroperabilityAPIView
from .day_of_views import PersonalOccurrenceDayOfAPIView, PersonalOccurrenceLiveAPIView
from .me_views import (
    PersonalCollectivesAPIView,
    PersonalConsiderationsAPIView,
    PersonalMeAPIView,
    PersonalPartnersAPIView,
    PersonalPassportAPIView,
    PersonalResourcesAPIView,
)
from .personal_views import PersonalNowAPIView, PersonalOngoingAPIView
from .now_media_views import PersonalNowJourneyArtifactMediaAPIView
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
    path(
        "now/media/journey-artifacts/<uuid:artifact_id>/",
        PersonalNowJourneyArtifactMediaAPIView.as_view(),
        name="now-journey-artifact-media",
    ),
    path("ongoing/", PersonalOngoingAPIView.as_view(), name="ongoing"),
    path("accesses/", PersonalAccessesAPIView.as_view(), name="accesses"),
    path("history/", PersonalHistoryAPIView.as_view(), name="history"),
    path("search/", PersonalSearchAPIView.as_view(), name="search"),
    path("interoperability/", PersonalInteroperabilityAPIView.as_view(), name="interoperability"),
    path(
        "occurrences/<uuid:pk>/day-of/",
        PersonalOccurrenceDayOfAPIView.as_view(),
        name="day-of",
    ),
    path(
        "occurrences/<uuid:pk>/live/",
        PersonalOccurrenceLiveAPIView.as_view(),
        name="live",
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
