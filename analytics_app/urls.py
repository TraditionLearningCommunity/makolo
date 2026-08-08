from django.urls import path

from .views import AnalyticsDashboardView, EventAnalyticsView


app_name = "analytics"

urlpatterns = [
    path("", AnalyticsDashboardView.as_view(), name="dashboard"),
    path("events/<slug:slug>/", EventAnalyticsView.as_view(), name="event-detail"),
]
