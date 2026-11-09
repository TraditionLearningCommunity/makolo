from django.urls import path
from commerce.personal_order_views import PersonalCommerceOrderDetailAPIView

from .access_views import PersonalAccessCredentialAPIView, PersonalAccessesAPIView
from .history_views import PersonalHistoryAPIView
from .search_views import PersonalSearchAPIView
from interoperability.api_views import PersonalInteroperabilityAPIView
from intelligence.connection_api import (
    ProfileIntelligenceConnectionsAPIView, ProfileIntelligenceConnectionAPIView,
)

from .day_of_views import PersonalOccurrenceDayOfAPIView, PersonalOccurrenceLiveAPIView
from .me_views import (
    PersonalCollectivesAPIView,
    PersonalConsiderationsAPIView,
    PersonalConsiderationSettingsAPIView,
    PersonalMeAPIView,
    PersonalMeTerritoryPreviewAPIView,
    PersonalPartnersAPIView,
    PersonalPassportAPIView,
    PersonalPassportPdfAPIView,
    PersonalPassportIssueAPIView,
    PersonalPassportHistoryAPIView,
    PersonalPassportVersionAPIView,
    PersonalPassportVersionPdfAPIView,
    PersonalPassportShareAPIView,
    PersonalPassportDirectShareAPIView,
    PersonalPassportShareRevokeAPIView,
    PersonalPassportVersionRevokeAPIView,
    PersonalResourcesAPIView,
)
from .passport_visibility_views import PersonalPassportVisibilityAPIView
from .personal_views import PersonalNowAPIView, PersonalOngoingAPIView
from .now_media_views import PersonalNowJourneyArtifactMediaAPIView
from .z9_views import PersonalPartnerDetailAPIView
from .trust_resources_views import (
    PersonalProofDetailAPIView,
    PersonalProofsAPIView,
    PersonalTitleDetailAPIView,
    PersonalTitlesAPIView,
)
from .z8_views import (
    PersonalGroupDetailAPIView,
    PersonalResourceArchiveAPIView,
    PersonalResourceCreateAPIView,
    PersonalResourceDetailAPIView,
    PersonalResourceVersionCreateAPIView,
    PersonalResourceVersionDownloadAPIView,
    PersonalResourceVersionReuseAPIView,
)


app_name = "personal-projections"

urlpatterns = [
    path("", PersonalMeAPIView.as_view(), name="me"),
    path("preview/<str:territory>/", PersonalMeTerritoryPreviewAPIView.as_view(), name="me-preview"),
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
    path("orders/<uuid:order_id>/", PersonalCommerceOrderDetailAPIView.as_view(), name="commerce-order-detail"),
    path("interoperability/", PersonalInteroperabilityAPIView.as_view(), name="interoperability"),
    path("intelligence/connections/", ProfileIntelligenceConnectionsAPIView.as_view(), name="intelligence-connections"),
    path("intelligence/connections/<uuid:connection_id>/", ProfileIntelligenceConnectionAPIView.as_view(), name="intelligence-connection"),
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
    path("considerations/settings/", PersonalConsiderationSettingsAPIView.as_view(), name="consideration-settings"),
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
    path("passport/visibility/", PersonalPassportVisibilityAPIView.as_view(), name="passport-visibility"),
    path("passport/pdf/", PersonalPassportPdfAPIView.as_view(), name="passport-pdf"),
    path("passport/issue/", PersonalPassportIssueAPIView.as_view(), name="passport-issue"),
    path("passport/history/", PersonalPassportHistoryAPIView.as_view(), name="passport-history"),
    path("passport/history/<uuid:snapshot_id>/", PersonalPassportVersionAPIView.as_view(), name="passport-version"),
    path("passport/history/<uuid:snapshot_id>/pdf/", PersonalPassportVersionPdfAPIView.as_view(), name="passport-version-pdf"),
    path("passport/history/<uuid:snapshot_id>/share/", PersonalPassportShareAPIView.as_view(), name="passport-share"),
    path("passport/history/<uuid:snapshot_id>/deliver/", PersonalPassportDirectShareAPIView.as_view(), name="passport-direct-delivery"),
    path("passport/history/<uuid:snapshot_id>/revoke/", PersonalPassportVersionRevokeAPIView.as_view(), name="passport-version-revoke"),
    path("passport/shares/<uuid:share_id>/revoke/", PersonalPassportShareRevokeAPIView.as_view(), name="passport-share-revoke"),
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
        "proofs/",
        PersonalProofsAPIView.as_view(),
        name="proofs",
    ),
    path(
        "proofs/<uuid:pk>/",
        PersonalProofDetailAPIView.as_view(),
        name="proof-detail",
    ),
    path(
        "titles/",
        PersonalTitlesAPIView.as_view(),
        name="titles",
    ),
    path(
        "titles/<uuid:pk>/",
        PersonalTitleDetailAPIView.as_view(),
        name="title-detail",
    ),

    path(
        "resources/create/",
        PersonalResourceCreateAPIView.as_view(),
        name="resource-create",
    ),
    path(
        "resources/<uuid:pk>/versions/",
        PersonalResourceVersionCreateAPIView.as_view(),
        name="resource-version-create",
    ),
    path(
        "resources/<uuid:pk>/archive/",
        PersonalResourceArchiveAPIView.as_view(),
        name="resource-archive",
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
