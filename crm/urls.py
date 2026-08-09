from django.urls import path

from .customer_views import (
    Contact360DetailView,
    Segment360CreateView,
    Segment360DetailView,
    Segment360EditView,
)
from .views import (
    CampaignCancelView,
    CampaignClickView,
    CampaignCreateView,
    CampaignDetailView,
    CampaignSendView,
    CampaignTemplateCreateView,
    CampaignTemplateEditView,
    ContactConsentUpdateView,
    ContactCustomValueUpdateView,
    ContactNoteCreateView,
    ContactTagAssignView,
    ContactTagRemoveView,
    CRMCustomFieldCreateView,
    CRMHomeView,
    CRMTagCreateView,
    OrganizationCRMView,
    UnsubscribeView,
)

app_name = "crm"

urlpatterns = [
    path("", CRMHomeView.as_view(), name="dashboard"),
    path("org/<slug:slug>/", OrganizationCRMView.as_view(), name="organization"),
    path("org/<slug:slug>/tags/new/", CRMTagCreateView.as_view(), name="tag-create"),
    path("org/<slug:slug>/fields/new/", CRMCustomFieldCreateView.as_view(), name="custom-field-create"),
    path("org/<slug:slug>/templates/new/", CampaignTemplateCreateView.as_view(), name="template-create"),
    path("templates/<uuid:pk>/edit/", CampaignTemplateEditView.as_view(), name="template-edit"),
    path("org/<slug:slug>/segments/new/", Segment360CreateView.as_view(), name="segment-create"),
    path("org/<slug:slug>/campaigns/new/", CampaignCreateView.as_view(), name="campaign-create"),
    path("contacts/<uuid:pk>/", Contact360DetailView.as_view(), name="contact-detail"),
    path("contacts/<uuid:pk>/notes/", ContactNoteCreateView.as_view(), name="contact-note"),
    path("contacts/<uuid:pk>/consent/", ContactConsentUpdateView.as_view(), name="contact-consent"),
    path("contacts/<uuid:pk>/tags/", ContactTagAssignView.as_view(), name="contact-tag-add"),
    path("contacts/<uuid:pk>/tags/<uuid:tag_id>/remove/", ContactTagRemoveView.as_view(), name="contact-tag-remove"),
    path("contacts/<uuid:pk>/fields/<uuid:field_id>/", ContactCustomValueUpdateView.as_view(), name="contact-field-update"),
    path("segments/<uuid:pk>/", Segment360DetailView.as_view(), name="segment-detail"),
    path("segments/<uuid:pk>/edit/", Segment360EditView.as_view(), name="segment-edit"),
    path("campaigns/<uuid:pk>/", CampaignDetailView.as_view(), name="campaign-detail"),
    path("campaigns/<uuid:pk>/send/", CampaignSendView.as_view(), name="campaign-send"),
    path("campaigns/<uuid:pk>/cancel/", CampaignCancelView.as_view(), name="campaign-cancel"),
    path("c/<str:token>/", CampaignClickView.as_view(), name="campaign-click"),
    path("unsubscribe/<str:token>/", UnsubscribeView.as_view(), name="unsubscribe"),
]
