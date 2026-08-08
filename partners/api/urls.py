from django.urls import path

from .views import (
    CampaignListAPIView,
    CommissionListAPIView,
    PartnerListAPIView,
    PartnerMetricsAPIView,
    PayoutListAPIView,
    ReferralCodeListAPIView,
)

app_name = "partners_api"

urlpatterns = [
    path("partners/", PartnerListAPIView.as_view(), name="partners"),
    path("campaigns/", CampaignListAPIView.as_view(), name="campaigns"),
    path("codes/", ReferralCodeListAPIView.as_view(), name="codes"),
    path("commissions/", CommissionListAPIView.as_view(), name="commissions"),
    path("payouts/", PayoutListAPIView.as_view(), name="payouts"),
    path("partners/<uuid:pk>/metrics/", PartnerMetricsAPIView.as_view(), name="partner-metrics"),
]
