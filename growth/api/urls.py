from django.urls import path

from .views import (
    CRMPresetsAPIView,
    FeedbackAPIView,
    GrowthOrganizationsAPIView,
    MarketingLinkListCreateAPIView,
    MarketingLinkToggleAPIView,
    OrganizationGrowthAPIView,
)


app_name = "growth_api"

urlpatterns = [
    path("organizations/", GrowthOrganizationsAPIView.as_view(), name="organizations"),
    path("organizations/<slug:slug>/", OrganizationGrowthAPIView.as_view(), name="organization"),
    path("links/", MarketingLinkListCreateAPIView.as_view(), name="links"),
    path("links/<uuid:pk>/toggle/", MarketingLinkToggleAPIView.as_view(), name="link-toggle"),
    path("feedback/", FeedbackAPIView.as_view(), name="feedback"),
    path("organizations/<slug:slug>/presets/", CRMPresetsAPIView.as_view(), name="presets"),
]
