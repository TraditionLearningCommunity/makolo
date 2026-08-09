from django.urls import path

from .views import (
    AnalyticsDashboardView,
    EventAnalyticsView,
    GrowthAnalyticsDashboardView,
    GrowthSpendCreateView,
    GrowthSpendDeleteView,
    OrganizationGrowthAnalyticsView,
)


app_name = "analytics"

urlpatterns = [
    path("", AnalyticsDashboardView.as_view(), name="dashboard"),
    path("events/<slug:slug>/", EventAnalyticsView.as_view(), name="event-detail"),
    path("growth/", GrowthAnalyticsDashboardView.as_view(), name="growth-dashboard"),
    path(
        "growth/o/<slug:slug>/",
        OrganizationGrowthAnalyticsView.as_view(),
        name="growth-organization",
    ),
    path(
        "growth/o/<slug:slug>/spend/new/",
        GrowthSpendCreateView.as_view(),
        name="growth-spend-new",
    ),
    path(
        "growth/spend/<uuid:pk>/delete/",
        GrowthSpendDeleteView.as_view(),
        name="growth-spend-delete",
    ),
]
