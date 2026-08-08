from django.urls import path

from .management_views import CampaignUpdateView, PartnerUpdateView, ReferralCodeToggleView
from .views import (
    CampaignCreateView,
    CampaignDetailView,
    OrganizationPartnerView,
    PartnerCreateView,
    PartnerDashboardView,
    PartnerDetailView,
    PayoutCancelView,
    PayoutCreateView,
    PayoutMarkPaidView,
    ReferralCodeCreateView,
    ReferralLandingView,
)

app_name = "partners"

urlpatterns = [
    path("", PartnerDashboardView.as_view(), name="dashboard"),
    path("r/<str:code>/", ReferralLandingView.as_view(), name="referral-landing"),
    path("org/<slug:slug>/", OrganizationPartnerView.as_view(), name="organization"),
    path("org/<slug:slug>/partners/new/", PartnerCreateView.as_view(), name="partner-create"),
    path("org/<slug:slug>/campaigns/new/", CampaignCreateView.as_view(), name="campaign-create"),
    path("campaigns/<uuid:pk>/", CampaignDetailView.as_view(), name="campaign-detail"),
    path("campaigns/<uuid:pk>/edit/", CampaignUpdateView.as_view(), name="campaign-edit"),
    path("campaigns/<uuid:pk>/codes/new/", ReferralCodeCreateView.as_view(), name="referral-create"),
    path("codes/<uuid:pk>/toggle/", ReferralCodeToggleView.as_view(), name="referral-toggle"),
    path("partners/<uuid:pk>/", PartnerDetailView.as_view(), name="partner-detail"),
    path("partners/<uuid:pk>/edit/", PartnerUpdateView.as_view(), name="partner-edit"),
    path("partners/<uuid:pk>/payouts/new/", PayoutCreateView.as_view(), name="payout-create"),
    path("payouts/<uuid:pk>/paid/", PayoutMarkPaidView.as_view(), name="payout-paid"),
    path("payouts/<uuid:pk>/cancel/", PayoutCancelView.as_view(), name="payout-cancel"),
]
