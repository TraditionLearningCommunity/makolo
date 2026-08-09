from django.urls import path

from .views import (
    CRMPresetActivateView,
    EventFeedbackSubmitView,
    GrowthDashboardView,
    MarketingLinkCreateView,
    MarketingLinkQrView,
    MarketingLinkToggleView,
    OrganizationFeedbackView,
    OrganizationGrowthView,
)


app_name = "growth"

urlpatterns = [
    path("", GrowthDashboardView.as_view(), name="dashboard"),
    path("o/<slug:slug>/", OrganizationGrowthView.as_view(), name="organization"),
    path("o/<slug:slug>/links/new/", MarketingLinkCreateView.as_view(), name="link-new"),
    path("links/<uuid:pk>/toggle/", MarketingLinkToggleView.as_view(), name="link-toggle"),
    path("links/<uuid:pk>/qr/", MarketingLinkQrView.as_view(), name="link-qr"),
    path("events/<slug:slug>/feedback/", EventFeedbackSubmitView.as_view(), name="feedback-submit"),
    path("o/<slug:slug>/feedback/", OrganizationFeedbackView.as_view(), name="feedback-list"),
    path(
        "o/<slug:slug>/presets/<slug:preset_key>/activate/",
        CRMPresetActivateView.as_view(),
        name="preset-activate",
    ),
]
