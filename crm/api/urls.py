from django.urls import path

from .customer360 import BehavioralSegmentListCreateAPIView, Customer360APIView
from .views import (
    CampaignCancelAPIView,
    CampaignListCreateAPIView,
    CampaignMetricsAPIView,
    CampaignSendAPIView,
    ContactConsentAPIView,
    ContactCustomFieldAPIView,
    ContactListAPIView,
    ContactTagAPIView,
    ContactTagDeleteAPIView,
    CustomFieldListCreateAPIView,
    SegmentListCreateAPIView,
    SegmentPreviewAPIView,
    TagListCreateAPIView,
    TemplateListCreateAPIView,
)

app_name = "crm_api"

urlpatterns = [
    path("contacts/", ContactListAPIView.as_view(), name="contacts"),
    path("contacts/<uuid:pk>/360/", Customer360APIView.as_view(), name="contact-360"),
    path("contacts/<uuid:pk>/consent/", ContactConsentAPIView.as_view(), name="contact-consent"),
    path("contacts/<uuid:pk>/tags/", ContactTagAPIView.as_view(), name="contact-tag-add"),
    path("contacts/<uuid:pk>/tags/<uuid:tag_id>/", ContactTagDeleteAPIView.as_view(), name="contact-tag-delete"),
    path("contacts/<uuid:pk>/fields/<uuid:field_id>/", ContactCustomFieldAPIView.as_view(), name="contact-field-value"),
    path("tags/", TagListCreateAPIView.as_view(), name="tags"),
    path("custom-fields/", CustomFieldListCreateAPIView.as_view(), name="custom-fields"),
    path("templates/", TemplateListCreateAPIView.as_view(), name="templates"),
    path("segments/", SegmentListCreateAPIView.as_view(), name="segments"),
    path("segments/behavioral/", BehavioralSegmentListCreateAPIView.as_view(), name="behavioral-segments"),
    path("segments/<uuid:pk>/preview/", SegmentPreviewAPIView.as_view(), name="segment-preview"),
    path("campaigns/", CampaignListCreateAPIView.as_view(), name="campaigns"),
    path("campaigns/<uuid:pk>/metrics/", CampaignMetricsAPIView.as_view(), name="campaign-metrics"),
    path("campaigns/<uuid:pk>/send/", CampaignSendAPIView.as_view(), name="campaign-send"),
    path("campaigns/<uuid:pk>/cancel/", CampaignCancelAPIView.as_view(), name="campaign-cancel"),
]
