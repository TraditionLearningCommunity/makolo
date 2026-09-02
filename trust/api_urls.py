from django.urls import path

from .api_views import DisputeAPIView, JourneyFeedbackAPIView, JourneyReportAPIView, MyProofsAPIView, PublicProofAPIView, PublicSpaceTrustAPIView

app_name = "trust_api"

urlpatterns = [
    path("spaces/<uuid:space_id>/summary/", PublicSpaceTrustAPIView.as_view(), name="space-summary"),
    path("journeys/<uuid:journey_id>/feedback/", JourneyFeedbackAPIView.as_view(), name="feedback"),
    path("journeys/<uuid:journey_id>/reports/", JourneyReportAPIView.as_view(), name="report-create"),
    path("disputes/<uuid:dispute_id>/", DisputeAPIView.as_view(), name="dispute-detail"),
    path("proofs/", MyProofsAPIView.as_view(), name="my-proofs"),
    path("proofs/verify/<uuid:public_id>/", PublicProofAPIView.as_view(), name="proof-verify"),
]
