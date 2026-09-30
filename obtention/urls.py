from django.urls import path

from .views import (
    ObtentionCreateView,
    ObtentionDetailView,
    ObtentionFulfillView,
    ObtentionJourneyView,
    ObtentionManageView,
    ObtentionOperatorReceiptView,
    ObtentionReceiptView,
    ObtentionRequirementAssessmentView,
    ObtentionStartView,
    ObtentionStepCompleteView,
    ObtentionStepStartView,
)


app_name = "obtention"

urlpatterns = [
    path("new/", ObtentionCreateView.as_view(), name="create"),
    path("<uuid:pk>/", ObtentionDetailView.as_view(), name="detail"),
    path("<uuid:pk>/manage/", ObtentionManageView.as_view(), name="manage"),
    path("<uuid:pk>/start/", ObtentionStartView.as_view(), name="start"),
    path("journeys/<uuid:pk>/", ObtentionJourneyView.as_view(), name="journey"),
    path("journeys/<uuid:pk>/targets/<uuid:target_id>/receive/", ObtentionReceiptView.as_view(), name="receipt"),
    path("journeys/<uuid:pk>/targets/<uuid:target_id>/confirm/", ObtentionOperatorReceiptView.as_view(), name="operator-confirm"),
    path("journeys/<uuid:pk>/fulfill/", ObtentionFulfillView.as_view(), name="fulfill"),
    path("journeys/<uuid:pk>/requirements/<uuid:assessment_id>/assess/", ObtentionRequirementAssessmentView.as_view(), name="requirement-assess"),
    path("journeys/<uuid:pk>/steps/<uuid:step_id>/start/", ObtentionStepStartView.as_view(), name="step-start"),
    path("journeys/<uuid:pk>/steps/<uuid:step_id>/complete/", ObtentionStepCompleteView.as_view(), name="step-complete"),
]
