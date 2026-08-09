from django.urls import path

from .views import (
    AnalyticsOverviewAPIView,
    EventAnalyticsAPIView,
    GrowthOrganizationsAPIView,
    GrowthSpendDetailAPIView,
    GrowthSpendListCreateAPIView,
    OrganizationGrowthAPIView,
)


app_name = "analytics_api"

urlpatterns = [
    path("overview/", AnalyticsOverviewAPIView.as_view(), name="overview"),
    path("events/<slug:slug>/", EventAnalyticsAPIView.as_view(), name="event-detail"),
    path("growth/organizations/", GrowthOrganizationsAPIView.as_view(), name="growth-organizations"),
    path(
        "growth/organizations/<slug:slug>/",
        OrganizationGrowthAPIView.as_view(),
        name="growth-organization",
    ),
    path("growth/spends/", GrowthSpendListCreateAPIView.as_view(), name="growth-spends"),
    path(
        "growth/spends/<uuid:pk>/",
        GrowthSpendDetailAPIView.as_view(),
        name="growth-spend-detail",
    ),
]
