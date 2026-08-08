from django.urls import path

from .views import AnalyticsOverviewAPIView, EventAnalyticsAPIView


app_name = "analytics_api"

urlpatterns = [
    path("overview/", AnalyticsOverviewAPIView.as_view(), name="overview"),
    path("events/<slug:slug>/", EventAnalyticsAPIView.as_view(), name="event-detail"),
]
