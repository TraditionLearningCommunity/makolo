from django.urls import path

from .api_views import JourneyResourceListAPIView


urlpatterns = [
    path("journeys/<uuid:journey_id>/resources/", JourneyResourceListAPIView.as_view(), name="journey-resource-list"),
]
