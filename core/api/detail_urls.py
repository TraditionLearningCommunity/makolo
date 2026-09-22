from django.urls import path

from .detail_views import (
    PersonalAccessDetailAPIView,
    PersonalJourneyDetailAPIView,
    PersonalJourneyRequirementDetailAPIView,
)

app_name = "personal-detail-projections"

urlpatterns = [
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
