from django.urls import path

from .operator_views import (
    ServiceArtifactDownloadView,
    ServiceAssignmentCreateView,
    ServiceAssignmentEndView,
    ServiceBlockerCreateView,
    ServiceBlockerResolveView,
    ServiceConfigurationView,
    ServiceNoteCreateView,
    ServiceOperatorCaseView,
    ServiceOperatorDashboardView,
    ServicePaymentEvidenceDecisionView,
    ServiceReviewDecisionView,
    ServiceReviewerQueueView,
    ServiceStepCompleteView,
    ServiceStepStartView,
)
from .participant_views import ParticipantArtifactUploadView, ParticipantArtifactVersionView, ParticipantExternalPaymentEvidenceView
from .views import ServiceCatalogView, ServiceIntakeView, ServiceStartView

app_name = "services"

urlpatterns = [
    path("", ServiceCatalogView.as_view(), name="list"),
    path("operator/", ServiceOperatorDashboardView.as_view(), name="operator-dashboard"),
    path("operator/reviews/", ServiceReviewerQueueView.as_view(), name="reviewer-queue"),
    path("operator/services/<uuid:service_pk>/", ServiceConfigurationView.as_view(), name="operator-service-config"),
    path("operator/journeys/<uuid:pk>/", ServiceOperatorCaseView.as_view(), name="operator-case"),
    path("operator/journeys/<uuid:pk>/steps/<uuid:step_pk>/start/", ServiceStepStartView.as_view(), name="operator-step-start"),
    path("operator/journeys/<uuid:pk>/steps/<uuid:step_pk>/complete/", ServiceStepCompleteView.as_view(), name="operator-step-complete"),
    path("operator/journeys/<uuid:pk>/blockers/new/", ServiceBlockerCreateView.as_view(), name="operator-blocker-create"),
    path("operator/journeys/<uuid:pk>/blockers/<uuid:blocker_pk>/resolve/", ServiceBlockerResolveView.as_view(), name="operator-blocker-resolve"),
    path("operator/journeys/<uuid:pk>/notes/new/", ServiceNoteCreateView.as_view(), name="operator-note-create"),
    path("operator/journeys/<uuid:pk>/assignments/new/", ServiceAssignmentCreateView.as_view(), name="operator-assignment-create"),
    path("operator/journeys/<uuid:pk>/assignments/<uuid:assignment_pk>/end/", ServiceAssignmentEndView.as_view(), name="operator-assignment-end"),
    path("operator/journeys/<uuid:pk>/evidence/<uuid:evidence_pk>/decision/", ServicePaymentEvidenceDecisionView.as_view(), name="operator-evidence-decision"),
    path("operator/reviews/<uuid:review_pk>/decision/", ServiceReviewDecisionView.as_view(), name="operator-review-decision"),
    path("operator/artifacts/<uuid:artifact_pk>/download/", ServiceArtifactDownloadView.as_view(), name="operator-artifact-download"),
    path("<uuid:pk>/start/", ServiceStartView.as_view(), name="start"),
    path("journeys/<uuid:pk>/intake/", ServiceIntakeView.as_view(), name="intake"),
    path("journeys/<uuid:pk>/artifacts/new/", ParticipantArtifactUploadView.as_view(), name="participant-artifact-upload"),
    path("artifacts/<uuid:artifact_pk>/new-version/", ParticipantArtifactVersionView.as_view(), name="participant-artifact-version"),
    path("journeys/<uuid:pk>/payments/<uuid:obligation_pk>/evidence/", ParticipantExternalPaymentEvidenceView.as_view(), name="participant-payment-evidence"),
]