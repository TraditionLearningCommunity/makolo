from django.urls import path

from .api_views import JourneyContextAPIView, LastMinuteAPIView


app_name = "spatiotemporal-api"
urlpatterns = [
    path("journeys/<uuid:journey_id>/context/", JourneyContextAPIView.as_view(), name="journey-context"),
    path("last-minute/", LastMinuteAPIView.as_view(), name="last-minute"),
]
