from django.urls import path

from .api_views import (
    ObtentionDetailAPIView,
    ObtentionFulfillAPIView,
    ObtentionJourneyAPIView,
    ObtentionJourneyCreateAPIView,
    ObtentionListCreateAPIView,
    ObtentionOperatorReceiptAPIView,
    ObtentionReceiptAPIView,
    ObtentionRequirementAssessmentAPIView,
    ObtentionStepCompleteAPIView,
    ObtentionStepStartAPIView,
)


app_name = "obtention_api"

urlpatterns = [
    path("", ObtentionListCreateAPIView.as_view(), name="list-create"),
    path("<uuid:pk>/", ObtentionDetailAPIView.as_view(), name="detail"),
    path("<uuid:pk>/journeys/", ObtentionJourneyCreateAPIView.as_view(), name="journey-create"),
    path("journeys/<uuid:pk>/", ObtentionJourneyAPIView.as_view(), name="journey-detail"),
    path("journeys/<uuid:pk>/targets/<uuid:target_id>/receipt/", ObtentionReceiptAPIView.as_view(), name="receipt"),
    path("journeys/<uuid:pk>/targets/<uuid:target_id>/operator-confirm/", ObtentionOperatorReceiptAPIView.as_view(), name="operator-confirm"),
    path("journeys/<uuid:pk>/fulfill/", ObtentionFulfillAPIView.as_view(), name="fulfill"),
    path("journeys/<uuid:pk>/requirements/<uuid:assessment_id>/assess/", ObtentionRequirementAssessmentAPIView.as_view(), name="requirement-assess"),
    path("journeys/<uuid:pk>/steps/<uuid:step_id>/start/", ObtentionStepStartAPIView.as_view(), name="step-start"),
    path("journeys/<uuid:pk>/steps/<uuid:step_id>/complete/", ObtentionStepCompleteAPIView.as_view(), name="step-complete"),
]
