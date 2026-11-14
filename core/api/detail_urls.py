from services.api_requirement_evidence import ServiceRequirementEvidenceAPIView
from journeys.api_artifacts import (
    JourneyArtifactCollectionAPIView,
    JourneyArtifactDownloadAPIView,
    JourneyArtifactVersionAPIView,
)

from .journey_invitation_api import PersonalJourneyInvitationAPIView
from django.urls import path

from .detail_views import (
    PersonalAccessDetailAPIView,
    PersonalJourneyDetailAPIView,
    PersonalJourneyRequirementDetailAPIView,
)

app_name = "personal-detail-projections"

urlpatterns = [
    path(
        "journeys/<uuid:journey_id>/requirements/<uuid:assessment_id>/evidence/",
        ServiceRequirementEvidenceAPIView.as_view(),
        name="journey-requirement-evidence",
    ),

    path(
        "journeys/<uuid:journey_id>/artifacts/",
        JourneyArtifactCollectionAPIView.as_view(),
        name="journey-artifacts",
    ),
    path(
        "journeys/<uuid:journey_id>/artifacts/<uuid:artifact_id>/versions/",
        JourneyArtifactVersionAPIView.as_view(),
        name="journey-artifact-version",
    ),
    path(
        "journeys/<uuid:journey_id>/artifacts/<uuid:artifact_id>/download/",
        JourneyArtifactDownloadAPIView.as_view(),
        name="journey-artifact-download",
    ),
    path("journeys/<uuid:pk>/invitation/", PersonalJourneyInvitationAPIView.as_view(), name="journey-invitation"),
    path(
        "journeys/<uuid:pk>/",
        PersonalJourneyDetailAPIView.as_view(),
        name="journey-detail",
    ),
    path(
        "journeys/<uuid:journey_id>/requirements/<uuid:assessment_id>/",
        PersonalJourneyRequirementDetailAPIView.as_view(),
        name="journey-requirement-detail",
    ),
    path(
        "accesses/<uuid:pk>/",
        PersonalAccessDetailAPIView.as_view(),
        name="access-detail",
    ),
]
