from django.urls import path

from .views import (
    CampaignCancelAPIView,
    CampaignListCreateAPIView,
    CampaignMetricsAPIView,
    CampaignSendAPIView,
    ContactConsentAPIView,
    ContactListAPIView,
    SegmentListCreateAPIView,
    SegmentPreviewAPIView,
)

app_name = "crm_api"

urlpatterns = [
    path("contacts/", ContactListAPIView.as_view(), name="contacts"),
    path("contacts/<uuid:pk>/consent/", ContactConsentAPIView.as_view(), name="contact-consent"),
    path("segments/", SegmentListCreateAPIView.as_view(), name="segments"),
    path("segments/<uuid:pk>/preview/", SegmentPreviewAPIView.as_view(), name="segment-preview"),
    path("campaigns/", CampaignListCreateAPIView.as_view(), name="campaigns"),
    path("campaigns/<uuid:pk>/metrics/", CampaignMetricsAPIView.as_view(), name="campaign-metrics"),
    path("campaigns/<uuid:pk>/send/", CampaignSendAPIView.as_view(), name="campaign-send"),
    path("campaigns/<uuid:pk>/cancel/", CampaignCancelAPIView.as_view(), name="campaign-cancel"),
]
