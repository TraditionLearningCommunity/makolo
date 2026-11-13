from django.urls import path

from preparation.space_api_views import (
    SpaceBeneficiaryResourcesAPIView,
    SpaceBeneficiaryResourceDownloadAPIView,
)

from journeys.api_artifacts import (
    JourneyArtifactCollectionAPIView,
    JourneyArtifactDownloadAPIView,
    JourneyArtifactVersionAPIView,
)
from services.space_beneficiary_api import (
    SpaceBeneficiaryServiceStartAPIView,
    SpaceBeneficiaryJourneyAPIView,
    SpaceBeneficiaryJourneyListAPIView,
    SpaceBeneficiaryIntakeAPIView,
    SpaceBeneficiaryRequirementAPIView,
)

from space_assets.api_views import (
    SpaceDocumentCollectionAPIView,
    SpaceDocumentDetailAPIView,
    SpaceDocumentVersionCreateAPIView,
    SpaceDocumentDownloadAPIView,
    SpaceDocumentReuseAPIView, SpaceDocumentEligibleJourneysAPIView, SpaceDocumentShareAPIView,
    SpaceDocumentShareRevokeAPIView,
)

from interoperability.api_views import SpaceInteroperabilityAPIView
from intelligence.connection_api import (
    SpaceIntelligenceConnectionsAPIView, SpaceIntelligenceConnectionAPIView,
)

from commerce.space_order_views import SpaceCommerceOrderDetailAPIView
from payments.space_obligation_views import SpacePayerObligationAPIView

from .public_space_views import PublicSpaceDetailAPIView, PublicSpacesAPIView
from .space_attention_views import SpaceDiscoverAPIView, SpaceNowAPIView
from .space_request_views import SpaceJourneyRequestAPIView
from .space_history_views import SpaceHistoryAPIView
from .space_search_views import SpaceSearchAPIView
from .space_mark_views import SpaceMarkAPIView
from .space_work_views import SpaceWorkAPIView
from .space_work_g2_case_views import SpaceG2ServiceCaseAPIView
from .space_work_g2_create import SpaceWorkG2CreateAPIView
from .space_work_g3_offer_views import SpaceWorkG3OfferAPIView
from .space_work_g3_transport_create import SpaceG3TransportCreateAPIView
from .space_work_g3_transport_operations import SpaceG3TransportDepartureOperationsAPIView
from .space_activity_create import SpaceG1ActivityCreateAPIView
from .space_zs4_views import (
    SpacePilotAPIView, SpaceRelationshipsAPIView, SpaceUsAPIView,
    SpaceUsAuthorityAPIView, SpaceUsResourcesAPIView,
)
from .space_passport_views import (
    SpacePassportAPIView, SpacePassportPdfAPIView, SpacePassportIssueAPIView,
    SpacePassportHistoryAPIView, SpacePassportVersionAPIView,
    SpacePassportVersionPdfAPIView, SpacePassportShareAPIView,
    SpacePassportDirectShareAPIView, SpacePassportVersionRevokeAPIView,
    SpacePassportShareRevokeAPIView,
)
from .views import FollowDetailAPIView, FollowListCreateAPIView, FollowTargetAPIView
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
    path(
        "workspaces/<slug:slug>/beneficiary/journeys/",
        SpaceBeneficiaryJourneyListAPIView.as_view(),
        name="workspace-beneficiary-journeys",
    ),
    path(
        "workspaces/<slug:slug>/beneficiary/journeys/<uuid:journey_id>/requirements/<uuid:assessment_id>/",
        SpaceBeneficiaryRequirementAPIView.as_view(),
        name="workspace-beneficiary-requirement",
    ),
    path(
        "workspaces/<slug:slug>/beneficiary/journeys/<uuid:journey_id>/resources/",
        SpaceBeneficiaryResourcesAPIView.as_view(),
        name="workspace-beneficiary-resources",
    ),
    path(
        "workspaces/<slug:slug>/beneficiary/journeys/<uuid:journey_id>/resources/<uuid:resource_id>/download/",
        SpaceBeneficiaryResourceDownloadAPIView.as_view(),
        name="workspace-beneficiary-resource-download",
    ),
    path(
        "workspaces/<slug:slug>/beneficiary/services/<uuid:pk>/start/",
        SpaceBeneficiaryServiceStartAPIView.as_view(),
        name="workspace-service-applicant-start",
    ),
    path(
        "workspaces/<slug:slug>/beneficiary/journeys/<uuid:journey_id>/",
        SpaceBeneficiaryJourneyAPIView.as_view(),
        name="workspace-beneficiary-journey",
    ),
    path(
        "workspaces/<slug:slug>/beneficiary/journeys/<uuid:journey_id>/intake/",
        SpaceBeneficiaryIntakeAPIView.as_view(),
        name="workspace-beneficiary-intake",
    ),
    path(
        "workspaces/<slug:slug>/beneficiary/journeys/<uuid:journey_id>/artifacts/",
        JourneyArtifactCollectionAPIView.as_view(),
        name="workspace-beneficiary-artifacts",
    ),
    path(
        "workspaces/<slug:slug>/beneficiary/journeys/<uuid:journey_id>/artifacts/<uuid:artifact_id>/versions/",
        JourneyArtifactVersionAPIView.as_view(),
        name="workspace-beneficiary-artifact-version",
    ),
    path(
        "workspaces/<slug:slug>/beneficiary/journeys/<uuid:journey_id>/artifacts/<uuid:artifact_id>/download/",
        JourneyArtifactDownloadAPIView.as_view(),
        name="workspace-beneficiary-artifact-download",
    ),
    path("public-spaces/", PublicSpacesAPIView.as_view(), name="public-spaces"),
    path("public-spaces/<slug:slug>/", PublicSpaceDetailAPIView.as_view(), name="public-space-detail"),
    path("workspaces/", SpaceWorkspaceListAPIView.as_view(), name="workspaces"),
    path("workspaces/<slug:slug>/", SpaceWorkspaceDetailAPIView.as_view(), name="workspace-detail"),
    path("workspaces/<slug:slug>/now/", SpaceNowAPIView.as_view(), name="workspace-now"),
    path("workspaces/<slug:slug>/requests/<uuid:request_id>/", SpaceJourneyRequestAPIView.as_view(), name="workspace-request-detail"),
    path("workspaces/<slug:slug>/discover/", SpaceDiscoverAPIView.as_view(), name="workspace-discover"),
    path("workspaces/<slug:slug>/work/", SpaceWorkAPIView.as_view(), name="workspace-work"),
    path("workspaces/<slug:slug>/work/service-cases/<uuid:journey_id>/", SpaceG2ServiceCaseAPIView.as_view(), name="workspace-service-case"),
    path("workspaces/<slug:slug>/work/g2/create/", SpaceWorkG2CreateAPIView.as_view(), name="workspace-work-g2-create"),
    path("workspaces/<slug:slug>/work/g3/activities/<uuid:activity_id>/offers/", SpaceWorkG3OfferAPIView.as_view(), name="workspace-work-g3-offer-create"),
    path("workspaces/<slug:slug>/work/g3/offers/<uuid:offer_id>/", SpaceWorkG3OfferAPIView.as_view(), name="workspace-work-g3-offer-edit"),
    path("workspaces/<slug:slug>/work/g3/transport/create/", SpaceG3TransportCreateAPIView.as_view(), name="workspace-work-g3-transport-create"),
    path("workspaces/<slug:slug>/work/g3/transport/departures/<uuid:departure_id>/operations/", SpaceG3TransportDepartureOperationsAPIView.as_view(), name="workspace-work-g3-departure-operations"),
    path("workspaces/<slug:slug>/work/activities/", SpaceG1ActivityCreateAPIView.as_view(), name="workspace-work-activity-create"),
    path("workspaces/<slug:slug>/history/", SpaceHistoryAPIView.as_view(), name="workspace-history"),
    path("workspaces/<slug:slug>/commerce/orders/<uuid:order_id>/", SpaceCommerceOrderDetailAPIView.as_view(), name="workspace-commerce-order-detail"),
    path("workspaces/<slug:slug>/payment-obligations/<uuid:obligation_id>/", SpacePayerObligationAPIView.as_view(), name="workspace-payment-obligation-detail"),
    path("workspaces/<slug:slug>/search/", SpaceSearchAPIView.as_view(), name="workspace-search"),
    path("workspaces/<slug:slug>/us/", SpaceUsAPIView.as_view(), name="workspace-us"),
    path("workspaces/<slug:slug>/us/authority/", SpaceUsAuthorityAPIView.as_view(), name="workspace-us-authority"),
    path("workspaces/<slug:slug>/us/resources/", SpaceUsResourcesAPIView.as_view(), name="workspace-us-resources"),
    path("workspaces/<slug:slug>/documents/", SpaceDocumentCollectionAPIView.as_view(), name="workspace-documents"),
    path("workspaces/<slug:slug>/documents/eligible-journeys/", SpaceDocumentEligibleJourneysAPIView.as_view(), name="workspace-documents-eligible-journeys"),
    path("workspaces/<slug:slug>/documents/<uuid:document_id>/", SpaceDocumentDetailAPIView.as_view(), name="workspace-document"),
    path("workspaces/<slug:slug>/documents/<uuid:document_id>/versions/", SpaceDocumentVersionCreateAPIView.as_view(), name="workspace-document-version-create"),
    path("workspaces/<slug:slug>/documents/versions/<uuid:version_id>/download/", SpaceDocumentDownloadAPIView.as_view(), name="workspace-document-download"),
    path("workspaces/<slug:slug>/documents/versions/<uuid:version_id>/reuse/", SpaceDocumentReuseAPIView.as_view(), name="workspace-document-reuse"),
    path("workspaces/<slug:slug>/documents/versions/<uuid:version_id>/share/", SpaceDocumentShareAPIView.as_view(), name="workspace-document-share"),
    path("workspaces/<slug:slug>/documents/shares/<uuid:delivery_id>/revoke/", SpaceDocumentShareRevokeAPIView.as_view(), name="workspace-document-share-revoke"),
    path("workspaces/<slug:slug>/passport/", SpacePassportAPIView.as_view(), name="workspace-passport"),
    path("workspaces/<slug:slug>/passport/pdf/", SpacePassportPdfAPIView.as_view(), name="workspace-passport-pdf"),
    path("workspaces/<slug:slug>/passport/issue/", SpacePassportIssueAPIView.as_view(), name="workspace-passport-issue"),
    path("workspaces/<slug:slug>/passport/history/", SpacePassportHistoryAPIView.as_view(), name="workspace-passport-history"),
    path("workspaces/<slug:slug>/passport/history/<uuid:snapshot_id>/", SpacePassportVersionAPIView.as_view(), name="workspace-passport-version"),
    path("workspaces/<slug:slug>/passport/history/<uuid:snapshot_id>/pdf/", SpacePassportVersionPdfAPIView.as_view(), name="workspace-passport-version-pdf"),
    path("workspaces/<slug:slug>/passport/history/<uuid:snapshot_id>/share/", SpacePassportShareAPIView.as_view(), name="workspace-passport-share"),
    path("workspaces/<slug:slug>/passport/history/<uuid:snapshot_id>/deliver/", SpacePassportDirectShareAPIView.as_view(), name="workspace-passport-direct"),
    path("workspaces/<slug:slug>/passport/history/<uuid:snapshot_id>/revoke/", SpacePassportVersionRevokeAPIView.as_view(), name="workspace-passport-version-revoke"),
    path("workspaces/<slug:slug>/passport/shares/<uuid:share_id>/revoke/", SpacePassportShareRevokeAPIView.as_view(), name="workspace-passport-share-revoke"),
    path("workspaces/<slug:slug>/relationships/", SpaceRelationshipsAPIView.as_view(), name="workspace-relationships"),
    path("workspaces/<slug:slug>/pilot/", SpacePilotAPIView.as_view(), name="workspace-pilot"),
    path("workspaces/<slug:slug>/archive/", SpaceArchiveAPIView.as_view(), name="workspace-archive"),
    path("workspaces/<slug:slug>/restore/", SpaceRestoreAPIView.as_view(), name="workspace-restore"),
    path("workspaces/<slug:slug>/ownership/transfer/", SpaceOwnershipTransferAPIView.as_view(), name="workspace-ownership-transfer"),
    path("workspaces/<slug:slug>/team/", SpaceTeamAPIView.as_view(), name="workspace-team"),
    path("workspaces/<slug:slug>/team/<uuid:membership_id>/", SpaceTeamMemberAPIView.as_view(), name="workspace-team-member"),
    path("workspaces/<slug:slug>/interoperability/", SpaceInteroperabilityAPIView.as_view(), name="workspace-interoperability"),
    path("workspaces/<slug:slug>/intelligence/connections/", SpaceIntelligenceConnectionsAPIView.as_view(), name="workspace-intelligence-connections"),
    path("workspaces/<slug:slug>/intelligence/connections/<uuid:connection_id>/", SpaceIntelligenceConnectionAPIView.as_view(), name="workspace-intelligence-connection"),
    path("workspaces/<slug:slug>/mark/", SpaceMarkAPIView.as_view(), name="workspace-mark"),
    path("follows/", FollowListCreateAPIView.as_view(), name="follows"),
    path("follows/<uuid:pk>/", FollowDetailAPIView.as_view(), name="follow-detail"),
    path("follows/targets/<str:kind>/<uuid:target_id>/", FollowTargetAPIView.as_view(), name="follow-target"),
]
