from django.urls import path

from .participant_views import ParticipantArtifactUploadView, ParticipantArtifactVersionView, ParticipantExternalPaymentEvidenceView
from .views import ServiceCatalogView, ServiceIntakeView, ServiceStartView

app_name = "services"

urlpatterns = [
    path("", ServiceCatalogView.as_view(), name="list"),
    path("<uuid:pk>/start/", ServiceStartView.as_view(), name="start"),
    path("journeys/<uuid:pk>/intake/", ServiceIntakeView.as_view(), name="intake"),
    path("journeys/<uuid:pk>/artifacts/new/", ParticipantArtifactUploadView.as_view(), name="participant-artifact-upload"),
    path("artifacts/<uuid:artifact_pk>/new-version/", ParticipantArtifactVersionView.as_view(), name="participant-artifact-version"),
    path("journeys/<uuid:pk>/payments/<uuid:obligation_pk>/evidence/", ParticipantExternalPaymentEvidenceView.as_view(), name="participant-payment-evidence"),
]
