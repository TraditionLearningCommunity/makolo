from django.urls import path

from .api_views import DisputeAPIView, JourneyFeedbackAPIView, JourneyReportAPIView, MyProofsAPIView, PublicProofAPIView, PublicSpaceTrustAPIView
from .credential_api_views import ActivityCredentialIssueAPIView, CredentialRevokeAPIView, MyCredentialsAPIView, PublicCredentialAPIView

app_name = "trust_api"

urlpatterns = [
    path("spaces/<uuid:space_id>/summary/", PublicSpaceTrustAPIView.as_view(), name="space-summary"),
    path("journeys/<uuid:journey_id>/feedback/", JourneyFeedbackAPIView.as_view(), name="feedback"),
    path("journeys/<uuid:journey_id>/reports/", JourneyReportAPIView.as_view(), name="report-create"),
    path("disputes/<uuid:dispute_id>/", DisputeAPIView.as_view(), name="dispute-detail"),
    path("proofs/", MyProofsAPIView.as_view(), name="my-proofs"),
    path("proofs/verify/<uuid:public_id>/", PublicProofAPIView.as_view(), name="proof-verify"),
    path("credentials/", MyCredentialsAPIView.as_view(), name="my-credentials"),
    path("activities/<uuid:activity_id>/credentials/", ActivityCredentialIssueAPIView.as_view(), name="credential-issue"),
    path("credentials/<uuid:credential_id>/revoke/", CredentialRevokeAPIView.as_view(), name="credential-revoke"),
    path("credentials/verify/<uuid:public_id>/", PublicCredentialAPIView.as_view(), name="credential-verify"),
]
