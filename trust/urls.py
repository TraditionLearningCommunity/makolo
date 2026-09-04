from django.urls import path

from .credential_views import PublicCredentialVerifyView
from .staff_proof_views import StaffProofQueueView, StaffProofRevokeView
from .views import (
    DisputeDetailView,
    EvidenceDownloadView,
    JourneyFeedbackView,
    JourneyReportView,
    MyProofsView,
    PublicProofVerifyView,
    PublicSpaceTrustView,
    ReportDetailView,
    SpaceTrustConsoleView,
    SpaceVerificationRequestView,
    StaffDisputeActionView,
    StaffReportActionView,
    StaffTrustQueueView,
    StaffVerificationActionView,
)

app_name = "trust"

urlpatterns = [
    path("spaces/<slug:slug>/", PublicSpaceTrustView.as_view(), name="space-public"),
    path("spaces/<slug:slug>/console/", SpaceTrustConsoleView.as_view(), name="space-console"),
    path("spaces/<slug:slug>/verification/request/", SpaceVerificationRequestView.as_view(), name="verification-request"),
    path("journeys/<uuid:journey_id>/feedback/", JourneyFeedbackView.as_view(), name="feedback"),
    path("journeys/<uuid:journey_id>/report/", JourneyReportView.as_view(), name="report-create"),
    path("reports/<uuid:report_id>/", ReportDetailView.as_view(), name="report-detail"),
    path("disputes/<uuid:dispute_id>/", DisputeDetailView.as_view(), name="dispute-detail"),
    path("evidence/<uuid:evidence_id>/", EvidenceDownloadView.as_view(), name="evidence-download"),
    path("proofs/", MyProofsView.as_view(), name="my-proofs"),
    path("proofs/verify/<uuid:public_id>/", PublicProofVerifyView.as_view(), name="proof-verify"),
    path("credentials/verify/<uuid:public_id>/", PublicCredentialVerifyView.as_view(), name="credential-verify"),
    path("staff/", StaffTrustQueueView.as_view(), name="staff-queue"),
    path("staff/proofs/", StaffProofQueueView.as_view(), name="staff-proof-queue"),
    path("staff/proofs/<uuid:proof_id>/revoke/", StaffProofRevokeView.as_view(), name="staff-proof-revoke"),
    path("staff/verifications/<uuid:claim_id>/", StaffVerificationActionView.as_view(), name="staff-verification-action"),
    path("staff/reports/<uuid:report_id>/", StaffReportActionView.as_view(), name="staff-report-action"),
    path("staff/disputes/<uuid:dispute_id>/", StaffDisputeActionView.as_view(), name="staff-dispute-action"),
]
