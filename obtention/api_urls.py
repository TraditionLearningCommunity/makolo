from django.urls import path

from .api_views import (
    ObtentionDetailAPIView,
    ObtentionFulfillAPIView,
    ObtentionJourneyAPIView,
    ObtentionJourneyCreateAPIView,
    ObtentionListCreateAPIView,
    ObtentionOperatorReceiptAPIView,
    ObtentionReceiptAPIView,
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
]
